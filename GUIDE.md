# Career Council — How It Works, Prerequisites, and Usage

This guide explains the **Career Council**: what it is, how the skill and the
`career-council` tool fit together, prerequisites, the pluggable model backends,
and how to operate it safely.

---

## 1. What the Career Council is

Asking one AI model "is my resume good?" gives you **one perspective with one set
of blind spots**. The Career Council instead runs the question through role-based
advisors — recruiter, hiring manager, career strategist, the skeptic, and mode
specialists — each pushing hard on a different angle, then has them
**peer-review each other anonymously**, and finally a **Career Director**
synthesizes a single decisive verdict plus one concrete next step.

It has four modes:

- **RESUME** — sharpen a CV / LinkedIn / profile for a target role.
- **STRATEGY** — plan the search: targeting, positioning, pipeline, dual-market split.
- **INTERVIEW** — prep for a specific interview / round, or run a mock.
- **OFFER** — evaluate and negotiate compensation.

The non-negotiable rule is **ground everything in the candidate's REAL materials**:
every claim quotes the actual resume line or job-description requirement. Advisors
**never invent** achievements, metrics, titles, or employers — anything missing is
flagged "needs your input", never fabricated.

This tool is a sibling of `dev-council` but **completely independent**: separate
command, separate `~/.career-council` config, separate budget meter. They share no
state and never interact.

---

## 2. The two pieces: the skill and the `career-council` tool

| Piece | Where | Responsibility |
|-------|-------|----------------|
| **`career-council` skill** | `~/.cursor/skills/career-council/SKILL.md` | The "brain": gathering your materials, framing the neutral brief, triaging mode/tier/roster, and presenting the verdict. |
| **`career-council` CLI/tool** | this repo (`career-council-runner`) | The "engine": runs each persona as its own agent **on its own model**, performs anonymized peer review, runs the Career Director, meters usage, and returns the verdict markdown. |

**Why two pieces?** An assistant's built-in `Task` sub-agents all run on the *same*
model — "one opinion wearing six hats." The `career-council` tool exists to give
each persona a genuinely **different model**, which is the entire value of a council.
The skill delegates execution to the tool.

---

## 3. How a run flows

```
You: "review my resume for this Principal AI Infra JD"
        │
        ▼
  [skill] gather materials + write the neutral brief + triage mode/tier/roster
        │  career-council run --mode resume --stakes thorough --cwd ./materials --brief-file brief.md
        ▼
  [tool] dispatch advisors ── each persona → its own backend + model (parallel)
        │                       cursor personas read the materials folder; provider
        │                       personas get the brief/context injected
        ▼
  [tool] anonymize responses (A/B/C…) → peer review (cross-family reviewers)
        │
        ▼
  [tool] Career Director synthesizes the de-anonymized analyses + peer reviews
        │
        ▼
  Verdict markdown  →  presented back to you
        │
        └─ one usage row per agent run appended to ~/.career-council/usage.jsonl
```

A single failed advisor never sinks the run — it is captured and the council continues.

---

## 4. The roster (personas)

A small **core** always runs; **specialists** join only at the `thorough` tier or via
an explicit `--roster`.

**Core (every mode):** Career Strategist, Recruiter / Talent Acquisition, Hiring
Manager, Candidate Advocate (Pragmatist), The Skeptic / Devil's Advocate.

**Specialists by mode:**
- **RESUME** — Resume/CV Writer, Personal Brand / LinkedIn, ATS / Keyword Optimizer.
- **STRATEGY** — Personal Brand / LinkedIn, Networking Strategist, Skills-Gap Advisor.
- **INTERVIEW** — Behavioral / STAR Coach, Technical Interviewer (AI Infra).
- **OFFER** — Compensation / Negotiation Expert.

Each persona is assigned a model by **capability** (heavy judgment lenses get strong
"thinking" models; light lenses get cheaper/faster ones) and **diversity** (roles are
spread across model families so they don't share blind spots). Peer reviewers are always
drawn from a **different family** than the advisor they grade.

Built with a **dual-market** search in mind (Israel primary + US / Boston / remote) for
senior AI-infrastructure roles: advisors state which market advice applies to and keep
the local vs US resume variants distinct.

---

## 5. Prerequisites

**Required (default Cursor backend):**

1. **Python 3.10+**.
2. **The tool installed:** `pip install -e .` from this repo (installs the `cursor-sdk`
   dependency and the `career-council` command).
3. **A Cursor API key** in `CURSOR_API_KEY` (user key or team service-account key from
   <https://cursor.com/dashboard/integrations>).
4. The `career-council` command on your **PATH** (pip prints the Scripts dir if not); or
   just use `python -m career_council`.

**Optional (provider backends):**

- `pip install 'career-council-runner[openai]'` + `OPENAI_API_KEY` (and optional
  `OPENAI_BASE_URL`) — also covers **AutoX** and other OpenAI-compatible gateways.
- `pip install 'career-council-runner[anthropic]'` + `ANTHROPIC_API_KEY`.
- `pip install 'career-council-runner[google]'` + `GOOGLE_API_KEY` / `GEMINI_API_KEY`.
- `pip install 'career-council-runner[all]'` for all three.

> Credentials come from environment variables only. Never commit a key.

---

## 6. Backends

Execution is **pluggable**; each persona declares a `backend` (default `cursor`).

| Backend | Grounding | Credentials | Notes |
|---------|-----------|-------------|-------|
| `cursor` *(default)* | **Grounded** — reads your materials folder | `CURSOR_API_KEY` | One key gives GPT/Codex + Claude + Gemini. Recommended. |
| `openai` | Prompt-context | `OPENAI_API_KEY` (+ optional `OPENAI_BASE_URL`) | Works against OpenAI and any OpenAI-compatible gateway (AutoX, ...). |
| `anthropic` | Prompt-context | `ANTHROPIC_API_KEY` | Native Claude API. |
| `google` | Prompt-context | `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Native Gemini API. |

Only the Cursor backend lets an advisor open files in the materials folder. Provider
backends are plain chat calls, so keep the candidate's materials in the brief itself.

---

## 7. Using it

### Through Cursor (recommended)

Just ask in plain language: *"review my resume for this JD"*, *"mock interview me for a
Principal AI Infra role"*, *"is this offer competitive?"* The skill frames, triages, and
drives the tool.

### Directly on the command line

```bash
career-council run --mode resume    --stakes thorough --cwd ./materials --brief-file brief.md
career-council run --mode interview --stakes standard --brief "Prep for a Principal AI Infra loop"
career-council run ... --dry-run           # preview personas/models/readiness, spend nothing
career-council run ... --dry-run --json    # same, machine-readable
career-council models      # models your key can use + per-persona resolution
career-council backends    # configured backends and whether their keys are set
career-council usage       # runs this month vs the soft budget ceiling
```

Useful `run` flags: `--stakes quick|standard|thorough`, `--roster k1,k2,...` (force specific
personas), `--brief` / `--brief-file` / stdin, `--out file.md`, `--no-peer-review` / `--peer-review`.

**Always preview with `--dry-run` first** to confirm the run is multi-model and see which
key/package to supply if anything is blocked.

---

## 8. Tiers (budget governance)

| Tier | Roster | Peer review | Use for |
|------|--------|-------------|---------|
| `trivial` | — | no | the tool refuses to convene |
| `quick` | core | no | a fast, cheap gut-check |
| `standard` *(default)* | core | no | everyday use |
| `thorough` | core + specialists | yes | a real application, a live interview, an offer |

`career-council usage` tracks runs against a soft monthly ceiling and warns as you approach it.

---

## 9. Security & secret hygiene

- **No secret is ever stored in the repo.** All credentials come from environment variables.
- The interactive key prompt hides input and only persists to your **user environment** if you say yes.
- Advisors run read-only: they analyze and draft suggestions; they never edit your files.
- Your resume and personal materials stay local (read by the grounded backend from `--cwd`).

---

## 10. Configuration & overrides

Defaults ship inside the package (`src/career_council/defaults/`). Override any subset by
dropping files into `~/.career-council/`:

- `personas.yaml` — rosters, per-persona model, `model_params`, and `backend`.
- `tiers.yaml` — which personas/stages run per tier and the budget ceiling.
- `backends.yaml` — backend definitions (type, credential env var, optional base_url).

Cursor model ids are validated at runtime against `career-council models`; an id your account
can't use falls back to the configured default, and unsupported model params are dropped with
a warning (the tool never invents a slug or sends an invalid param).

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `career-council: command not found` | The Scripts dir isn't on PATH. Use `python -m career_council`, or add the dir pip printed at install. |
| `... model list came back empty` | Cursor discovery failed (network/key). Run `career-council models`; check `CURSOR_API_KEY`. |
| Key is set but reported **missing** | Stale editor environment: the editor captured its env at launch. On Windows the CLI self-heals from the registry; otherwise fully reopen the editor, or set it for the current shell. |
| A single persona shows `status=error` | Captured and reported; the council still produces a verdict. Check `~/.career-council/usage.jsonl`. |
| First command is slow (~10–20s) | The Cursor SDK bridge cold-starts. Subsequent calls in the same session are faster. |
