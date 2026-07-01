"""Standalone multi-model Career Council runner.

Each advisor persona (recruiter, hiring manager, career strategist, interviewer,
negotiator, ...) runs as its own agent on a different model via a pluggable
backend (Cursor SDK by default; OpenAI/AutoX, Anthropic, Google optional), reads
your real materials (resume, job description, notes) or injected context, is
peer-reviewed anonymously, and a Career Director synthesizes a decisive verdict.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
