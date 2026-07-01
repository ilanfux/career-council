"""Parallel advisor dispatch across pluggable backends.

Each persona runs on its configured backend and model. Cursor-backed personas
run as grounded local agents that read the materials folder; provider-backed
personas get a bounded materials-context snapshot injected into their prompt.
Tasks are grouped by backend, and the backend groups run concurrently (each
backend also parallelizes its own set internally). A single failed persona is
captured as a failed AdvisorResult and never sinks the run.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from career_council.backends import BackendRegistry, BackendTask
from career_council.context import gather_repo_context
from career_council.input import AdvisorResult, AgentOutcome, PersonaSpec
from career_council.metering import MeteringSink
from career_council.prompts import build_advisor_prompt


def dispatch_advisors(
    personas: List[PersonaSpec],
    brief: str,
    mode: str,
    cwd: str,
    diff_scope: Optional[str],
    meter: MeteringSink,
    registry: BackendRegistry,
) -> List[AdvisorResult]:
    if not personas:
        return []

    # Compute the materials-context snapshot at most once, and only if a
    # non-grounded backend actually needs it.
    _ctx: Dict[str, str] = {}

    def repo_context() -> str:
        if "value" not in _ctx:
            _ctx["value"] = gather_repo_context(cwd, diff_scope)
        return _ctx["value"]

    tasks_by_backend: Dict[str, List[BackendTask]] = defaultdict(list)
    warned_empty = False
    for persona in personas:
        grounded = registry.get(persona.backend).grounded
        ctx: Optional[str] = None
        if not grounded:
            ctx = repo_context()
            if not ctx and not warned_empty:
                print(
                    f"warning: no groundable materials found in --cwd for non-grounded "
                    f"backend '{persona.backend}'; provider advisors will rely only on the "
                    f"brief. Put the resume/JD text under --cwd or paste it into the brief.",
                    file=sys.stderr,
                )
                warned_empty = True
        prompt = build_advisor_prompt(
            persona,
            brief,
            mode,
            diff_scope,
            repo_context=ctx,
            grounded=grounded,
        )
        tasks_by_backend[persona.backend].append(
            BackendTask(task_id=persona.key, prompt=prompt, model=persona.model, params=persona.model_params)
        )

    outcomes_by_key: Dict[str, AgentOutcome] = {}

    def _run_group(item):
        backend_name, tasks = item
        backend = registry.get(backend_name)
        return list(zip(tasks, backend.run_batch(tasks, cwd=cwd)))

    # Run each backend group concurrently. For the common single-backend config
    # this is one worker (identical to sequential); hybrids fan out.
    with ThreadPoolExecutor(max_workers=max(1, len(tasks_by_backend))) as pool:
        for pairs in pool.map(_run_group, list(tasks_by_backend.items())):
            for task, outcome in pairs:
                outcomes_by_key[task.task_id] = outcome

    results: List[AdvisorResult] = []
    for persona in personas:
        outcome = outcomes_by_key.get(
            persona.key,
            AgentOutcome(status="error", text="", error_message="no outcome returned"),
        )
        meter.record("advisor", persona.key, persona.model, persona.family, outcome, backend=persona.backend)
        results.append(AdvisorResult(persona=persona, outcome=outcome))
    return results
