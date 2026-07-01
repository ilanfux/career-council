"""Prompt templates for advisors, peer reviewers, and the Career Director.

These mirror the career-council skill so the standalone runner produces the same
grounded, anonymized, peer-reviewed output. The non-negotiable rule is that every
claim is grounded in the candidate's REAL materials (resume, job description,
experience, notes) — advisors never invent achievements, metrics, titles, or
employers.
"""

from __future__ import annotations

from typing import Dict, List

from career_council.input import AdvisorResult, PersonaSpec

_ADVISOR_TEMPLATE = """You are the {title} on a Career Council helping a real person with their job search.

Your lens: {lens}

The brief:
---
{brief}
---

Mode: {mode}
{grounding}
Rules:
{read_rule}
- Ground every claim in the candidate's REAL materials: quote the actual resume line, the specific JD requirement, or the stated experience. Cite the source.
- NEVER fabricate achievements, metrics, titles, dates, or employers. If a point needs a metric the candidate hasn't given, mark it "needs your input" and say exactly what to ask them — do not invent it.
- State which market (Israel / US) a piece of advice applies to whenever the two differ, and keep the local (IL) and US resume variants distinct.
- Lean fully into your lens. Do NOT hedge or try to be balanced - other advisors cover the angles you don't. Synthesis comes later.
- If this mode/stage genuinely doesn't touch your lens, say so in ONE line and stop. Don't manufacture concerns.
{length_rule}
{mode_line}
{persona_line}"""

_DEFAULT_LENGTH_RULE = "- 150-300 words. No preamble. Be concrete and specific to THIS person."

_MODE_LINES = {
    "resume": (
        "- Propose concrete rewrites for weak lines (quantified, impact-first), and note where the IL and US variants must differ."
    ),
    "strategy": (
        "- Be concrete about targeting, positioning and the dual-market split; give named next actions, not generic advice."
    ),
    "interview": (
        "- Give likely questions and what a strong PRINCIPAL-level answer must contain, mapped to the candidate's real experience."
    ),
    "offer": (
        "- Give real market ranges for the level and market (ILS total-cost vs USD base+equity+bonus) and a concrete counter script."
    ),
}

_PERSONA_LINES = {
    "ghostwriter_detector": """- Run an explicit AI-writing detection checklist and flag EVERY instance with exact snippet + location:
  - Punctuation tells: em dashes (—), spaced en dashes ( – ), arrow glyphs (→), spaced slashes ( / ), middot separators (·), curly/smart quotes/apostrophes.
  - Sentence-pattern tells: repeated rule-of-three triads, "not just X, but Y", "it's not X, it's Y", "from X to Y", uniform bullet cadence, suspiciously balanced parallel structure.
  - Vocabulary tells: leverage, robust, seamless, delve, tapestry, underscore, pivotal, testament, landscape, realm, showcase, elevate, meticulous, comprehensive, cutting-edge, spearheaded, "in today's fast-paced", "at the intersection of", empty intensifiers, manifesto lines, over-hedging.
  - Structural tells: section pre-summaries, Title-Case overuse, templated heading symmetry.
- Rewrite hard rules:
  - Preserve every fact, metric, claim, and ownership boundary exactly.
  - Never invent, inflate, or delete substantive content.
  - Respect strict length constraints (for resumes: 2-page max); every addition must be paid by a cut.
  - Rewrite into plain, ATS-safe engineer voice: commas/periods/parentheses/colons over exotic punctuation.
- Output contract (use these exact sections):
  1) AI-likelihood score (0-100) + one-line justification.
  2) Line-by-line flag table: Location | Offending snippet | Why it reads AI | Human rewrite.
  3) Top 5 highest-signal fixes (max suspicion reduction per unit effort).
  4) Projected AI-likelihood score (0-100) after applying all fixes.
- Keep the output compact but complete; prioritize the table and concrete rewrites over prose."""
}

_PEER_REVIEW_TEMPLATE = """{n} advisors independently analyzed this career {topic_noun}:
---
{brief}
---
Anonymized responses:
{anonymized}

Answer, referencing responses by letter, under 200 words:
1. Which response is strongest and most grounded in the candidate's real materials, and why?
2. Which has the biggest blind spot, weakest-supported claim, or (worst) an invented/ungrounded suggestion? Call it out.
3. What did ALL responses miss that the council must consider (especially dual-market or level-realism angles)?"""

_TOPIC_NOUNS = {
    "resume": "resume/profile question",
    "strategy": "job-search strategy question",
    "interview": "interview-prep question",
    "offer": "offer/negotiation question",
}

_CHAIRMAN_TEMPLATE = """You are the Career Director of a Career Council. You receive the brief, every
advisor's de-anonymized analysis, and every peer review. Make the decisive call.

You are decisive: give a real recommendation, not "it depends". You may overrule
the majority when a dissenter's evidence is stronger. Stay grounded in the
candidate's real materials; never invent achievements or findings. Explicitly
resolve any Israel-vs-US or level-realism (is "Principal / Architect" the right
target?) tension.

If the Ghostwriter Detector persona is present, you MUST include a dedicated
Human-Voice Authenticity section with:
- before/after AI-likelihood scores,
- conflicts where de-AI-ing a line might weaken a strong truthful claim,
- the final agreed authenticity edits.
If Ghostwriter Detector was not convened, explicitly say so in that section.

The brief:
---
{brief}
---

Advisor analyses (de-anonymized):
{advisor_block}

Peer reviews:
{peer_block}

Produce the verdict in GitHub-flavored markdown, no preamble, using EXACTLY this structure:

{verdict_skeleton}"""

_RESUME_SKELETON = """## Career Council Verdict (Resume): <topic>
_Convened: <advisors> - skipped: <specialists + why>_

### Where the council agrees
<high-confidence points multiple advisors converged on, independently>

### Where the council clashes
<genuine disagreements - both sides + why each is reasonable (e.g. Advocate vs Skeptic on level)>

### Blind spots the council caught
<things that only surfaced in peer review>

### Human-Voice Authenticity
- AI-likelihood before fixes: <0-100 or 'not run'>
- AI-likelihood after agreed fixes: <0-100 or 'not run'>
- Conflict reconciliation: <where authenticity edits could weaken truthful strong claims, and final decision>
- Final authenticity edits: <the accepted edit set>

### Israel vs US
<what to do differently per market / the two-resume split>

### The recommendation
<a clear, decisive call - not "it depends">

### The one thing to do first
<a single concrete next step>"""

_STRATEGY_SKELETON = """## Career Council Verdict (Strategy): <topic>
_Convened: <advisors> - skipped: <specialists + why>_

### Where the council agrees
<high-confidence points multiple advisors converged on, independently>

### Where the council clashes
<genuine disagreements - both sides + why each is reasonable>

### Blind spots the council caught
<things that only surfaced in peer review>

### Human-Voice Authenticity
- AI-likelihood before fixes: <0-100 or 'not run'>
- AI-likelihood after agreed fixes: <0-100 or 'not run'>
- Conflict reconciliation: <where authenticity edits could weaken truthful strong claims, and final decision>
- Final authenticity edits: <the accepted edit set>

### Israel vs US
<how the search/positioning should differ per market>

### The recommendation
<a clear, decisive positioning + targeting call>

### The one thing to do first
<a single concrete next step>"""

_INTERVIEW_SKELETON = """## Career Council Verdict (Interview): <role @ company>
_Convened: <advisors> - skipped: <specialists + why>_

### Likely questions (and what a strong answer needs)
- <question> - what a principal-level answer must contain, grounded in the candidate's real experience

### Your strongest stories to lead with
<mapped to the candidate's real experience>

### Where you're exposed (drill these)
<gaps the Skeptic + Technical Interviewer found>

### Human-Voice Authenticity
- AI-likelihood before fixes: <0-100 or 'not run'>
- AI-likelihood after agreed fixes: <0-100 or 'not run'>
- Conflict reconciliation: <where authenticity edits could weaken truthful strong claims, and final decision>
- Final authenticity edits: <the accepted edit set>

### The one thing to prep first
<a single concrete next step>"""

_OFFER_SKELETON = """## Career Council Verdict (Offer): <role @ company>
_Convened: <advisors> - skipped: <specialists + why>_

### Is it competitive?
<market read for the level + market: base / equity / bonus>

### Leverage you actually have
<grounded - competing offers, scarcity, US citizenship for US roles>

### The counter (script)
<concrete numbers + wording>

### Human-Voice Authenticity
- AI-likelihood before fixes: <0-100 or 'not run'>
- AI-likelihood after agreed fixes: <0-100 or 'not run'>
- Conflict reconciliation: <where authenticity edits could weaken truthful strong claims, and final decision>
- Final authenticity edits: <the accepted edit set>

### Walk-away line
<the candidate's floor>"""

_SKELETONS = {
    "resume": _RESUME_SKELETON,
    "strategy": _STRATEGY_SKELETON,
    "interview": _INTERVIEW_SKELETON,
    "offer": _OFFER_SKELETON,
}


def build_advisor_prompt(
    persona: PersonaSpec,
    brief: str,
    mode: str,
    diff_scope: str | None,
    repo_context: str | None = None,
    grounded: bool = True,
) -> str:
    """Build the advisor prompt.

    `grounded` backends (Cursor) read the materials folder, so we tell the agent
    to read it. Non-grounded (provider) backends get `repo_context` (or, more
    usefully for career, the materials already pasted into the brief) and are told
    to ground strictly in what they can see.
    """

    mode_line = _MODE_LINES.get(mode, "")
    persona_line = _PERSONA_LINES.get(persona.key, "")
    length_rule = _DEFAULT_LENGTH_RULE if not persona_line else ""
    if grounded:
        grounding = "Working directory: the folder holding the candidate's materials (resume, JD, notes) you can read with your tools."
        if diff_scope:
            grounding += f"\nFocus: {diff_scope}"
        read_rule = "- Read the candidate's ACTUAL materials before forming any opinion (read/grep/glob the folder)."
    else:
        grounding = (repo_context or "").strip() or "(the candidate's materials are in the brief above)"
        read_rule = (
            "- Base your analysis strictly on the materials in the brief/context above. "
            "Do not invent or assume experience you cannot see."
        )
    return _ADVISOR_TEMPLATE.format(
        title=persona.title,
        lens=persona.lens,
        brief=brief,
        mode=mode.upper(),
        grounding=grounding,
        read_rule=read_rule,
        length_rule=length_rule,
        mode_line=mode_line,
        persona_line=persona_line,
    )


def build_peer_review_prompt(brief: str, mode: str, anonymized_map: Dict[str, str]) -> str:
    topic_noun = _TOPIC_NOUNS.get(mode, "career question")
    anonymized = "\n\n".join(f"**{letter}:** {text}" for letter, text in anonymized_map.items())
    return _PEER_REVIEW_TEMPLATE.format(
        n=len(anonymized_map),
        topic_noun=topic_noun,
        brief=brief,
        anonymized=anonymized,
    )


def build_chairman_prompt(
    brief: str,
    mode: str,
    advisors: List[AdvisorResult],
    peer_reviews: List[str],
) -> str:
    advisor_block = "\n\n".join(
        f"### {a.persona.title} (model: {a.persona.model})\n{a.outcome.text.strip()}"
        for a in advisors
        if a.outcome.ok
    )
    peer_block = (
        "\n\n".join(f"- {text.strip()}" for text in peer_reviews if text.strip())
        if peer_reviews
        else "(peer review not run for this tier)"
    )
    skeleton = _SKELETONS.get(mode, _STRATEGY_SKELETON)
    return _CHAIRMAN_TEMPLATE.format(
        brief=brief,
        advisor_block=advisor_block or "(no advisor produced a usable response)",
        peer_block=peer_block,
        verdict_skeleton=skeleton,
    )
