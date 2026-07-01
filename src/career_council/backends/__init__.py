"""Pluggable execution backends for the council."""

from career_council.backends.base import Backend, BackendError, BackendTask
from career_council.backends.registry import BackendRegistry

__all__ = ["Backend", "BackendError", "BackendTask", "BackendRegistry"]
