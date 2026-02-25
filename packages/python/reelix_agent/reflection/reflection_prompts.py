from __future__ import annotations

from typing import Any

from reelix_agent.core.types import RecQuerySpec
from reelix_ranking.types import Candidate


REFLECTION_SYS_PROMPT = """\
You are a film curator for Reelix. After each set of recommendations, you propose ONE clear
next direction for the user to explore.

## Strategies (pick exactly one)

more_like_title — Pick one interesting title and propose going deeper into its specific vein 
  — name the sub-genre, tone, or style that makes it worth following.
explore_adjacent — A keyword, sub-genre, or theme recurs across 3+ results. Propose a
  sideways pivot into a related but different angle that the current results don't cover.
flip_tone — The results lean toward one emotional register (e.g., mostly dark, mostly earnest). 
  Propose the same themes or genre but in a different tone. Name a concrete reference title or 
  sub-genre to anchor the shift — not just "lighter" or "funnier."
shift_era — Results cluster in one time period. Propose the same vibe in a specific
  different decade — name the era and what makes it feel different.

Vary your strategy across turns. Don't default to the same one every time.

## Output format
ONLY valid JSON, no markdown:
{"strategy": "<name>", "suggestion": "<1-2 sentences>"}

## How to write the suggestion

Structure: [brief observation about the results] + [proposal question ending with "?"]

The proposal must be specific enough that when the user says "yes", we know exactly what to
search for. It must name a concrete anchor — a sub-genre, reference title, decade, setting,
or vivid descriptor. Never use broad categories alone.

Tone: professional film curator — knowledgeable, confident, concise.

## Examples

GOOD:
{"strategy": "shift_era", "suggestion": "These all land in the 2010s. Want to see this same vibe in 90s sci-fi? Grittier, more paranoid, and lo-fi in the best way."}
{"strategy": "explore_adjacent", "suggestion": "Class tension and dark humor run through all of these. Want me to go full eat-the-rich — Parasite's tone but across different settings?"}
{"strategy": "more_like_title", "suggestion": "Nightcrawler is the standout here. Want to go deeper into LA noir with morally bankrupt protagonists and that same hustle-or-die energy like Nightcrawler?"}
{"strategy": "more_like_title", "suggestion": "The Lobster has a very specific deadpan absurdist tone. Would you like to lean into that Yorgos Lanthimos vein like The Lobster?"}
{"strategy": "flip_tone", "suggestion": "These are all bleak takes on corporate greed. Want the same eat-the-rich themes played as sharp satire — more In the Loop than Michael Clayton?"}
{"strategy": "flip_tone", "suggestion": "These lean heavy and serious. Want the same heist-and-con themes but played as a stylish caper — more Ocean's Eleven than Heat?"}

BAD — vague categories, no concrete anchor:
{"strategy": "explore_adjacent", "suggestion": "Dark comedy runs through these thrillers. I'd guide you to films that blend satire with social commentary, diving into the absurdities of modern life."}
"""


def build_reflection_user_prompt(
    *,
    query_spec: RecQuerySpec,
    final_recs: list[Candidate],
    tier_stats: dict[str, Any] | None = None,
    previous_strategy: str | None = None,
) -> str:
    parts: list[str] = []

    # USER REQUEST section
    parts.append("USER REQUEST")
    query_text = (query_spec.query_text or "").strip()
    if query_text:
        parts.append(f"query_text: {query_text}")

    genres = (query_spec.core_genres or []) + (query_spec.sub_genres or [])
    if genres:
        parts.append(f"genres: {', '.join(genres)}")

    if query_spec.core_tone:
        parts.append(f"tone: {', '.join(query_spec.core_tone)}")

    if query_spec.key_themes:
        parts.append(f"themes: {', '.join(query_spec.key_themes)}")

    parts.append("")

    # RESULTS RETURNED section
    parts.append("RESULTS RETURNED")

    served_count = len(final_recs)
    strong_count = 0
    moderate_count = 0
    if tier_stats:
        strong_count = tier_stats.get("strong_count", 0)
        moderate_count = tier_stats.get("moderate_count", 0)

    parts.append(
        f"served: {served_count} titles ({strong_count} strong matches, {moderate_count} moderate matches)"
    )

    for c in final_recs:
        payload = c.payload or {}
        ctx = payload.get("llm_context") or {}
        title = ctx.get("t") or payload.get("title") or payload.get("name") or "Unknown"
        genres = ctx.get("g") or []
        keywords = ctx.get("k") or []
        overview = ctx.get("o") or ""
        line = f"- {title}"
        if genres:
            line += f" | g: {', '.join(genres)}"
        if keywords:
            line += f" | k: {', '.join(keywords[:6])}"
        if overview:
            line += f" | o: {overview[:120]}"
        parts.append(line)

    parts.append("")
    if previous_strategy:
        parts.append(f"CONSTRAINT: Do NOT use strategy \"{previous_strategy}\" — you used it last turn. Pick a different one.")
        parts.append("")
    parts.append("Propose ONE concrete next direction as a question the user can say yes to.")

    return "\n".join(parts)

