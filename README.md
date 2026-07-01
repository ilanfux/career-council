# Career Council Runner

A standalone, host-agnostic CLI that runs a **multi-model career council**: each advisor
persona (recruiter, hiring manager, career strategist, technical interviewer, negotiator,
...) runs as its own agent on a **different model** (GPT/Codex, Claude, Gemini), reads your
real materials (resume, job description, notes), and grounds every claim in them — **never
inventing achievements**. Responses are anonymized, peer-reviewed, and a **Career Director**
synthesizes a decisive verdict plus one concrete next step.

It has four modes:

- **RESUME** — sharpen a CV / LinkedIn / profile for a target role.
- **STRATEGY** — plan the search: targeting, positioning, pipeline, dual-market split.
- **INTERVIEW** — prep for a specific interview / round, or run a mock.
- **OFFER** — evaluate and negotiate compensation.

Execution is **pluggable** across backends: the default [Cursor SDK](https://cursor.com/docs/sdk/python)
backend runs grounded local agents that read your materials folder, and optional provider
backends (`openai` — also covers AutoX/OpenAI-compatible gateways — `anthropic`, `google`)
let you bring your own per-model keys. Backend is per-persona, so you can run a hybrid.

> This is a sibling of, but fully independent from, the `dev-council` runner: its own
> command (`career-council`), its own `~/.career-council` config, its own budget meter.
> The two share no state and never interact — they just started from the same engine.

## Why

Asking one model gives you one set of blind spots. Running advisors on different model
**families** de-correlates those blind spots, which is the whole point of a council. This
runner makes "a different model per persona" the default, while keeping every advisor
grounded in your actual resume and target job description.

## Install

```bash
pip install -e /path/to/career-council-runner

# optional provider backends (bring your own keys):
pip install -e '/path/to/career-council-runner[openai]'   # OpenAI / AutoX / compatible
pip install -e '/path/to/career-council-runner[all]'      # openai + anthropic + google
```

Set your Cursor key (a user key or team service-account key):

```bash
export CURSOR_API_KEY="cursor_..."     # bash / zsh
$env:CURSOR_API_KEY = "cursor_..."     # PowerShell
```

Credentials are read from environment variables only — never commit a key. If a needed key
is missing, the CLI prompts for it (hidden) and can save it to your user environment.

> If the `career-council.exe` script isn't on your PATH, use `python -m career_council ...`
> everywhere in place of `career-council ...`.

## Quick start

```bash
# Confirm which models your key can actually use (Claude/Gemini included?)
career-council models

# Preview the plan WITHOUT spending anything (personas, models, readiness)
career-council run --mode resume --stakes thorough --cwd ./my-materials --brief-file brief.md --dry-run

# RESUME review at the thorough tier (full roster + specialists + peer review)
career-council run --mode resume --stakes thorough --cwd ./my-materials --brief-file brief.md

# Run only the human-voice authenticity audit lens
career-council run --mode resume --cwd ./my-materials --brief-file brief.md --roster ghostwriter_detector

# INTERVIEW prep (brief on stdin), standard tier
echo "Prep me for a Principal AI Infra interview at <company>" | career-council run --mode interview

# See spend vs your soft monthly ceiling, and backend credential readiness
career-council usage
career-council backends
```

`--cwd` should point at a folder holding your real materials (resume, JD, notes) so the
grounded advisors can read and quote them.

## Tiers (budget governance)

| Tier | Roster | Peer review | Use for |
|------|--------|-------------|---------|
| `trivial` | none | no | the tool refuses to convene |
| `quick` | core only | no | a fast, cheap gut-check |
| `standard` (default) | core only | no | everyday use — the five essential lenses |
| `thorough` | core + specialists | yes | a real application, a live interview, an offer |

The diverse, expensive roster + peer review only runs at `thorough`. Everything else stays cheap.

## Configuration

Defaults ship inside the package (`src/career_council/defaults/`). Override any of them by
copying into `~/.career-council/`:

- `personas.yaml` — the RESUME/STRATEGY/INTERVIEW/OFFER rosters: each persona's lens, model, `model_params`, and `backend`.
- `tiers.yaml` — which personas/stages run per tier, and the soft budget ceiling.
- `backends.yaml` — backend definitions (type, credential env var, optional base_url).

Model ids in `personas.yaml` are validated at runtime against `career-council models`; any
id your account cannot use falls back to the configured default (the tool never invents a
slug).

## How it maps to the `career-council` skill

The Cursor `career-council` skill owns framing (gather your materials + write the neutral
brief), triage (pick mode/tier/roster), and verdict presentation. Instead of spawning
advisors with the internal `Task` tool (which collapses onto one model), it calls
`career-council run ...`, and this runner performs the dispatch, anonymized peer review,
and Career Director synthesis with true per-persona models.
