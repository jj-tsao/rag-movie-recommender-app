from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from reelix_agent.core.types import RecQuerySpec
from reelix_agent.reflection.reflection_prompts import (
    REFLECTION_SYS_PROMPT,
    build_reflection_user_prompt,
)

if TYPE_CHECKING:
    from reelix_llm.client import LlmClient
    from reelix_ranking.types import Candidate

log = logging.getLogger(__name__)

REFLECTION_MODEL = "gpt-4o-mini"


@dataclass
class ReflectionResult:
    strategy: str
    suggestion: str
    input_tokens: int | None = None
    output_tokens: int | None = None


def _parse_reflection_response(raw: str) -> ReflectionResult | None:
    """Parse the JSON response from the reflection LLM call."""
    text = raw.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Reflection agent returned non-JSON: %s", text[:200])
        return None

    strategy = data.get("strategy", "")
    suggestion = data.get("suggestion", "")
    if not suggestion:
        return None
    return ReflectionResult(strategy=strategy, suggestion=suggestion)


async def generate_next_steps(
    *,
    chat_llm: "LlmClient",
    query_spec: RecQuerySpec,
    final_recs: list["Candidate"],
    tier_stats: dict[str, Any] | None = None,
    previous_strategy: str | None = None,
    model: str = REFLECTION_MODEL,
) -> ReflectionResult | None:
    """
    Generate a targeted next-step suggestion based on the query and results.

    Returns a ReflectionResult with strategy + suggestion, or None if the call fails.
    """
    if not final_recs:
        return None

    user_prompt = build_reflection_user_prompt(
        query_spec=query_spec,
        final_recs=final_recs,
        tier_stats=tier_stats,
        previous_strategy=previous_strategy,
    )

    messages = [
        {"role": "system", "content": REFLECTION_SYS_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        resp = await chat_llm.chat(
            messages=messages,
            model=model,
            temperature=0.5,
            max_tokens=200,
        )
        content = resp.choices[0].message.content
        if not content:
            return None
        result = _parse_reflection_response(content)
        if result and resp.usage:
            result.input_tokens = resp.usage.prompt_tokens
            result.output_tokens = resp.usage.completion_tokens
        return result
    except Exception:
        log.exception("Reflection agent failed")
        return None
