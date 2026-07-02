"""Thin, defensive wrapper around the Cursor SDK.

All interaction with the beta `cursor-sdk` package is isolated here so the rest
of the tool is insulated from surface changes.

Why async: the SDK's *synchronous* bridge reads its subprocess startup line with
`select.select()`, which on Windows only works on sockets (not pipes) and fails
with WinError 10038. The *async* bridge uses asyncio subprocess streams, which
work on Windows under the Proactor event loop. So we drive everything through the
async API and bridge each stage through a defensive loop runner.
"""

from __future__ import annotations

import atexit
import asyncio
import contextlib
import gc
import os
import sys
import threading
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from career_council.input import AgentOutcome

# A model selection is either a plain id string or a built ModelSelection dict.
ModelSpec = Union[str, Mapping[str, Any]]
# (task_id, prompt, model_spec) - task_id is opaque, used only to align results.
AgentTask = Tuple[str, str, ModelSpec]
# model id -> {param id -> set of allowed values}. Empty value-set means "any".
ModelParamCatalog = Dict[str, Dict[str, Set[str]]]

_WINDOWS_POLICY_LOCK = threading.Lock()
_WINDOWS_ASYNC_RUN_LOCK = threading.Lock()
_WINDOWS_LOOP_WORKER_LOCK = threading.Lock()
_WINDOWS_POLICY_SET = False
_WINDOWS_LOOP_WORKER: Optional["_WindowsLoopWorker"] = None
_CURSOR_SDK_WINDOWS_PATCHED = False
_BRIDGE_LAUNCH_MAX_ATTEMPTS = 3


def build_model_selection(model_id: str, params: Optional[Mapping[str, str]] = None) -> Any:
    """Return a plain id string, or a ModelSelection dict when params are set.

    The SDK accepts `model` as `str | ModelSelection | Mapping`. Params are
    family-specific (GPT/Codex use `reasoning`, Claude uses `effort`/`thinking`).
    """

    if not params:
        return model_id
    return {"id": model_id, "params": [{"id": str(k), "value": str(v)} for k, v in params.items()]}


class SdkUnavailableError(RuntimeError):
    """Raised when cursor-sdk is not importable or no API key is configured."""


def _require_api_key(explicit: Optional[str] = None) -> str:
    api_key = explicit or os.environ.get("CURSOR_API_KEY")
    if not api_key or not api_key.strip():
        raise SdkUnavailableError(
            "CURSOR_API_KEY is not set. Export your Cursor user or service-account "
            "key (see https://cursor.com/dashboard/integrations) before running the council."
        )
    return api_key.strip()


def _import_sdk():
    try:
        import cursor_sdk  # type: ignore
    except Exception as error:  # pragma: no cover - environment dependent
        raise SdkUnavailableError(
            "cursor-sdk is not installed. Install it with `pip install cursor-sdk` "
            f"(underlying error: {error})."
        ) from error
    _patch_cursor_sdk_windows_teardown(cursor_sdk)
    return cursor_sdk


def _patch_cursor_sdk_windows_teardown(cursor_sdk_module) -> None:
    """Patch cursor-sdk bridge teardown on Windows to close pipe transports.

    Without this, CPython 3.12 on Windows may emit `I/O operation on closed pipe`
    from asyncio transport finalizers at interpreter shutdown. We patch narrowly:
    keep upstream termination behavior, then explicitly close any subprocess pipe
    transports while the event loop is still alive.
    """

    global _CURSOR_SDK_WINDOWS_PATCHED
    if sys.platform != "win32" or _CURSOR_SDK_WINDOWS_PATCHED:
        return
    with _WINDOWS_POLICY_LOCK:
        if _CURSOR_SDK_WINDOWS_PATCHED:
            return
        try:
            from cursor_sdk import _async_bridge  # type: ignore
        except Exception:
            return

        original_terminate = getattr(_async_bridge, "_terminate_process", None)
        if original_terminate is None:
            return

        async def _patched_terminate_process(process):
            try:
                await original_terminate(process)
            finally:
                _close_subprocess_pipe_transports(process)
                with contextlib.suppress(Exception):
                    await asyncio.sleep(0)

        _async_bridge._terminate_process = _patched_terminate_process
        _CURSOR_SDK_WINDOWS_PATCHED = True


def _close_subprocess_pipe_transports(process) -> None:
    """Best-effort close of asyncio subprocess pipe transports."""

    transport = getattr(process, "_transport", None)
    get_pipe_transport = getattr(transport, "get_pipe_transport", None)
    if callable(get_pipe_transport):
        for fd in (0, 1, 2):
            with contextlib.suppress(Exception):
                pipe_transport = get_pipe_transport(fd)
                if pipe_transport is not None and not pipe_transport.is_closing():
                    pipe_transport.close()

    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(process, stream_name, None)
        stream_transport = getattr(stream, "_transport", None)
        if stream_transport is not None:
            with contextlib.suppress(Exception):
                if not stream_transport.is_closing():
                    stream_transport.close()


def _run_async(coro):
    """Run a coroutine on a fresh loop with defensive Windows shutdown.

    The Cursor async bridge uses subprocess pipes. On Windows, aggressively
    creating/closing loops can race transport finalizers and surface noisy
    `BaseSubprocessTransport.__del__` / `I/O operation on closed pipe` errors.
    We set Proactor policy once, serialize bridge runs, and flush pending loop
    callbacks before closing the loop.
    """

    _ensure_windows_proactor_policy()
    if sys.platform == "win32":
        # Keep bridge subprocess lifecycle deterministic on Windows.
        with _WINDOWS_ASYNC_RUN_LOCK:
            return _get_windows_loop_worker().run(coro)
    return _run_on_fresh_loop(coro)


def _ensure_windows_proactor_policy() -> None:
    global _WINDOWS_POLICY_SET
    if sys.platform != "win32" or _WINDOWS_POLICY_SET:
        return
    with _WINDOWS_POLICY_LOCK:
        if _WINDOWS_POLICY_SET:
            return
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        _WINDOWS_POLICY_SET = True


def _run_on_fresh_loop(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        _shutdown_loop(loop)
        asyncio.set_event_loop(None)


class _WindowsLoopWorker:
    """Single long-lived loop for Windows asyncio subprocess stability."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop = asyncio.new_event_loop()
        self._closed = False
        self._thread = threading.Thread(
            target=self._thread_main,
            name="career-council-asyncio",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait()

    def _thread_main(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()
        _shutdown_loop(self._loop)
        asyncio.set_event_loop(None)

    def run(self, coro):
        if self._closed:
            raise RuntimeError("Windows asyncio runner is closed")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)


def _get_windows_loop_worker() -> _WindowsLoopWorker:
    global _WINDOWS_LOOP_WORKER
    with _WINDOWS_LOOP_WORKER_LOCK:
        if _WINDOWS_LOOP_WORKER is None:
            _WINDOWS_LOOP_WORKER = _WindowsLoopWorker()
            atexit.register(_close_windows_loop_worker)
        return _WINDOWS_LOOP_WORKER


def _close_windows_loop_worker() -> None:
    global _WINDOWS_LOOP_WORKER
    with _WINDOWS_LOOP_WORKER_LOCK:
        worker = _WINDOWS_LOOP_WORKER
        _WINDOWS_LOOP_WORKER = None
    if worker is not None:
        worker.close()


def _shutdown_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Best-effort loop shutdown without leaking subprocess transports."""

    with contextlib.suppress(Exception):
        loop.run_until_complete(asyncio.sleep(0))

    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        with contextlib.suppress(Exception):
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

    with contextlib.suppress(Exception):
        loop.run_until_complete(loop.shutdown_asyncgens())
    with contextlib.suppress(Exception):
        loop.run_until_complete(loop.shutdown_default_executor())

    # Encourage transport finalizers to run while the loop is still alive.
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            gc.collect()
        with contextlib.suppress(Exception):
            loop.run_until_complete(asyncio.sleep(0))

    with contextlib.suppress(Exception):
        loop.close()


def _run_with_bridge_retry(coro_factory):
    """Retry transient bridge-launch failures (mostly Windows subprocess races)."""

    for attempt in range(1, _BRIDGE_LAUNCH_MAX_ATTEMPTS + 1):
        try:
            return _run_async(coro_factory())
        except Exception as error:
            if attempt >= _BRIDGE_LAUNCH_MAX_ATTEMPTS or not _is_retryable_bridge_launch_error(error):
                raise
            time.sleep(0.5 * attempt)


def _is_retryable_bridge_launch_error(error: Exception) -> bool:
    message = _safe_str(error).lower()
    markers = (
        "timed out waiting for bridge discovery",
        "bridge exited before discovery",
        "missing value for --tool-callback-auth-token",
        "invalid uuid",
    )
    return any(marker in message for marker in markers)


def _fetch_raw_models(api_key: Optional[str] = None):
    """Launch the bridge once and return the raw models.list() payload."""

    key = _require_api_key(api_key)
    sdk = _import_sdk()

    async def _run():
        async with await sdk.AsyncClient.launch_bridge(
            workspace=os.getcwd(), allow_api_key_env_fallback=True
        ) as client:
            return await client.list_models(api_key=key)

    return _run_with_bridge_retry(_run)


def list_models(api_key: Optional[str] = None) -> List[str]:
    """Return the model ids the calling account can use, best-effort."""

    return _extract_model_ids(_fetch_raw_models(api_key))


def discover_models(api_key: Optional[str] = None) -> Tuple[List[str], ModelParamCatalog]:
    """Return (available model ids, per-model supported param catalog) in one call.

    The param catalog lets the caller validate family-specific params (GPT/Codex
    `reasoning`, Claude `effort`/`thinking`, Gemini none) before sending them, so a
    config typo is dropped with a warning instead of failing a run at the bridge.
    """

    raw = _fetch_raw_models(api_key)
    return _extract_model_ids(raw), _extract_model_params(raw)


def run_agents_batch(tasks: Sequence[AgentTask], cwd: str, api_key: Optional[str] = None) -> List[AgentOutcome]:
    """Run several one-shot local agents concurrently against `cwd`.

    Uses a single async bridge and `asyncio.gather`, preserving task order in the
    returned list. A startup failure (CursorAgentError: never executed) and a run
    failure (RunResult.status == 'error') are normalized distinctly. One failed
    task never sinks the batch.
    """

    if not tasks:
        return []
    key = _require_api_key(api_key)
    sdk = _import_sdk()
    cursor_agent_error = getattr(sdk, "CursorAgentError", Exception)

    async def _one(client, prompt: str, model: ModelSpec) -> AgentOutcome:
        try:
            result = await sdk.AsyncAgent.prompt(
                prompt,
                sdk.AgentOptions(api_key=key, model=model, local=sdk.LocalAgentOptions(cwd=cwd)),
                client=client,
            )
        except cursor_agent_error as error:  # startup failure: never executed
            return AgentOutcome(status="startup_error", text="", error_message=_safe_str(getattr(error, "message", error)))
        except Exception as error:  # unexpected; treat as startup failure
            return AgentOutcome(status="startup_error", text="", error_message=_safe_str(error))
        return _normalize_result(result)

    async def _run() -> List[AgentOutcome]:
        async with await sdk.AsyncClient.launch_bridge(
            workspace=cwd, local=sdk.LocalAgentOptions(cwd=cwd), allow_api_key_env_fallback=True
        ) as client:
            return await asyncio.gather(*[_one(client, prompt, model) for (_id, prompt, model) in tasks])

    return _run_with_bridge_retry(_run)


def run_agent(prompt: str, model: ModelSpec, cwd: str, api_key: Optional[str] = None) -> AgentOutcome:
    """Convenience wrapper for a single one-shot agent run."""

    return run_agents_batch([("single", prompt, model)], cwd=cwd, api_key=api_key)[0]


def _normalize_result(result) -> AgentOutcome:
    status = _safe_str(getattr(result, "status", "finished")) or "finished"
    text = _safe_str(getattr(result, "result", "") or getattr(result, "text", ""))
    run_id = _opt_str(getattr(result, "id", None))
    agent_id = _opt_str(getattr(result, "agent_id", None))
    duration_ms = _opt_int(getattr(result, "duration_ms", None))
    # When a ModelSelection (dict/object) is sent, the SDK echoes it back; record
    # just the id so metering stays a clean model name.
    raw_model = getattr(result, "model", None)
    if isinstance(raw_model, Mapping):
        raw_model = raw_model.get("id", raw_model)
    actual_model = _opt_str(getattr(raw_model, "id", raw_model))

    if status == "error":
        return AgentOutcome(
            status="error",
            text=text,
            run_id=run_id,
            agent_id=agent_id,
            error_message="agent run reported status=error",
            duration_ms=duration_ms,
            actual_model=actual_model,
        )
    return AgentOutcome(
        status="finished",
        text=text,
        run_id=run_id,
        agent_id=agent_id,
        duration_ms=duration_ms,
        actual_model=actual_model,
    )


def _unwrap_items(raw):
    """models.list() may return a list or a wrapper with .data/.models/.items."""

    items = raw
    for attr in ("data", "models", "items"):
        if hasattr(items, attr):
            items = getattr(items, attr)
            break
    return items


def _entry_id(entry) -> Optional[str]:
    if isinstance(entry, str):
        return entry
    model_id = getattr(entry, "id", None) or (entry.get("id") if isinstance(entry, dict) else None)
    return str(model_id) if model_id else None


def _extract_model_ids(raw) -> List[str]:
    """Pull model id strings out of whatever shape models.list() returns."""

    ids: List[str] = []
    try:
        for entry in _unwrap_items(raw):
            model_id = _entry_id(entry)
            if model_id:
                ids.append(model_id)
    except TypeError:
        pass
    return ids


def _extract_model_params(raw) -> ModelParamCatalog:
    """Map each model id to its supported parameters and allowed values.

    A model with no parameters (e.g. Gemini) maps to an empty dict. Values are
    captured so we can also reject out-of-range values, not just unknown params.
    """

    catalog: ModelParamCatalog = {}
    try:
        for entry in _unwrap_items(raw):
            model_id = _entry_id(entry)
            if not model_id or isinstance(entry, str):
                continue
            params = getattr(entry, "parameters", None)
            if params is None and isinstance(entry, dict):
                params = entry.get("parameters")
            param_map: Dict[str, Set[str]] = {}
            for p in params or []:
                pid = getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else None)
                if not pid:
                    continue
                raw_values = getattr(p, "values", None)
                if raw_values is None and isinstance(p, dict):
                    raw_values = p.get("values")
                values: Set[str] = set()
                for v in raw_values or []:
                    val = getattr(v, "value", None) or (v.get("value") if isinstance(v, dict) else None)
                    if val is not None:
                        values.add(str(val))
                param_map[str(pid)] = values
            catalog[model_id] = param_map
    except TypeError:
        pass
    return catalog


def _safe_str(value) -> str:
    try:
        return "" if value is None else str(value)
    except Exception:
        return ""


def _opt_str(value) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _opt_int(value) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
