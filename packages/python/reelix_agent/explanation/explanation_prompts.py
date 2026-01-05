import hashlib
import json
import re
import time
from typing import Any

from reelix_agent.core.types import LLMCall, PromptsEnvelope, RecQuerySpec
from reelix_ranking.types import Candidate

WHY_SYS_PROMPT = """
You are a professional film curator and critic. Explain, for each provided candidate title, why it fits the user’s tastes. Use only the supplied candidates.

Your job:
Given (1) the user’s `query_text` and intents and (2) a ranked list of recommended titles with metadata,
write concise, high-precision “Why you might enjoy it” rationales for the user.


Principles:
1) Use ONLY the provided candidates, in the SAME order.
2) Be specific and spoiler-light (tone, themes, craft, performances, pacing, storytelling).
3) Style: concise, authoritative; 2-3 sentences per item. Avoid clichés and generic praise.

## Output Format (JSONL; streamable)
For each input item, output EXACTLY one JSON object on its own line (JSON Lines). 
End EVERY object with a real newline (actual line break). Preserve the input order.

Schema per line (keys must match exactly and be double-quoted):
{"media_id":"<id>","why":"<spoiler-light markdown tied to the user’s query>"}


## Rules
- One object per line. No extra text before, between, or after the JSON lines. No blank lines.
- The "why" value MUST be single-line markdown: do not include newline characters.
- Do NOT include the two-character sequence \\n anywhere in the output.
"""


def _sanitize_code_block(block: str) -> str:
    return re.sub(r"```", "``\u200b`", block or "")


def build_why_user_prompt(
    *,
    candidates: list[Candidate],
    query_spec: RecQuerySpec,
    batch_size: int = 8,
) -> str:
    parts: list[str] = []

    n_items = min(batch_size, len(candidates))
    query_text = (query_spec.query_text or "").strip()
    genres = (query_spec.core_genres or []) + (query_spec.sub_genres or [])

    parts.append("USER_REQUEST")
    if query_text:
        parts.append(f"query_text: {query_text}")

    if genres:
        parts.append(f"genres: {', '.join(genres)}")

    if query_spec.core_tone:
        parts.append(f"core_tone: {', '.join(query_spec.core_tone)}")

    if query_spec.key_themes:
        parts.append(f"key_themes: {', '.join(query_spec.key_themes)}")

    if query_spec.narrative_shape:
        parts.append(f"narrative_shape: {', '.join(query_spec.narrative_shape)}")

    parts.append("")
    parts.append(f"CANDIDATES (use all, keep order, total={n_items})")
    parts.append(
        "Each candidate block is self-contained. Do not mix details across candidates."
    )

    for c in candidates[:n_items]:
        payload = c.payload or {}
        media_id = str(payload.get("media_id", "")).strip()
        ctx = _sanitize_code_block(str(payload.get("embedding_text", "")).strip())

        parts.append("```")
        parts.append(f"media_id: {media_id}")
        parts.append(ctx)
        parts.append("```")

    parts.append("INSTRUCTIONS")
    parts.append(
        f"- Output exactly {n_items} JSONL objects (one per line), matching the candidate order."
    )

    return "\n".join(parts)


def build_why_prompt_envelope(
    *,
    candidates: list[Candidate],
    query_spec: RecQuerySpec,
    batch_size: int = 8,
    llm_model: str = "gpt-4o-mini",
    llm_params: dict[str, Any] | None = None,
) -> PromptsEnvelope:
    items_brief: list[dict[str, Any]] = []
    for c in candidates:
        p = getattr(c, "payload", {}) or {}
        items_brief.append(
            {
                "media_id": p.get("media_id"),
                "title": p.get("title") or p.get("name") or "Unknown",
            }
        )
    
    params = {"temperature": 0.7, "top_p": 1.0}
    if llm_params:
        params.update(llm_params)
        
    user_prompt = build_why_user_prompt(candidates=candidates, query_spec=query_spec, batch_size=batch_size)
    
    call = LLMCall(
        call_id=1,
        messages=[
            {"role": "system", "content": WHY_SYS_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        items_brief=items_brief,
    )
    
    envelope = PromptsEnvelope(
        model=llm_model,
        params=params,
        output={"format": "jsonl", "schema_version": "1"},
        calls=[call],
        prompt_hash=_prompt_hash(
            model=llm_model,
            params=params,
            output={"format": "jsonl", "schema_version": "1"},
            calls=[call],
        ),
        created_at=time.time(),
    )
    
    return envelope

def _prompt_hash(
    *,
    model: str,
    params: dict[str, Any],
    output: dict[str, Any],
    calls: list[LLMCall],
) -> str:
    """
    Canonicalize the parts that affect generation for deterministic traceability.
    """
    canon = {
        "model": model,
        "params": params,
        "output": output,
        "calls": [
            {"messages": c.messages}  # only messages affect model behavior
            for c in calls
        ],
    }
    b = json.dumps(
        canon, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(b).hexdigest()
