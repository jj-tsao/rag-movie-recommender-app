from __future__ import annotations

import re
from typing import Iterable, List, Mapping, Optional
from datetime import datetime, timezone
from reelix_core.types import UserSignals, BuildParams, MediaId
from reelix_ranking.types import Candidate
from reelix_user.signals.weights import compute_item_weights
from reelix_user.signals.selectors import select_titles_for_prompt

DEFAULT_LIMITS = dict(
    genres=7,
    keywords=12,
    pos=7,
    neg=2,
)


# == User prompt builder for for-you feed discovery mode ==
def build_for_you_user_prompt(
    *,
    candidates: List[Candidate],
    user_signals: UserSignals,
    query_text: Optional[str] = None,
    limits: Mapping[str, int] = DEFAULT_LIMITS,
    batch_size: int = 8,
    params: BuildParams = BuildParams(),
) -> str:
    """
    Build the User Prompt for the discover/for-you/why LLM call.
    Returns:
        Markdown string for the User Prompt to send to LLM.
    """

    # helpers
    def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
        seen = set()
        out = []
        for x in items:
            x = (x or "").strip()
            if x and x.lower() not in seen:
                seen.add(x.lower())
                out.append(x)
        return out

    def _cap(items: Iterable[str], k: int) -> list[str]:
        out = list(items)
        return out[: max(0, int(k))]

    def _csv(items: Iterable[str]) -> str:
        xs = [x.strip() for x in items if x and x.strip()]
        return ", ".join(xs) if xs else "(none)"

    def _sanitize_code_block(block: str) -> str:
        # Replace any standalone ``` with indented fence
        return re.sub(r"```", "``\u200b`", block or "")

    # context attributes
    now = datetime.now(timezone.utc)

    # compute canonical weight per title
    weights = compute_item_weights(user_signals.interactions, now, params)

    # select positive and negative titles by weights
    pos_ids, neg_ids = select_titles_for_prompt(
        weights,
        K_pos=limits.get("pos", 7),
        K_neg=limits.get("neg", 5),
    )

    titles_by_media: dict[MediaId, str] = {
        it.media_id: it.title
        for it in user_signals.interactions
        if getattr(it, "title", None)
    }

    pos_titles = [titles_by_media[mid] for mid in pos_ids if mid in titles_by_media]
    neg_titles = [titles_by_media[mid] for mid in neg_ids if mid in titles_by_media]

    # apply dedupe + caps
    genres = _cap(
        _dedupe_keep_order(user_signals.genres_include), limits.get("genres", 7)
    )
    keywords = _cap(
        _dedupe_keep_order(user_signals.keywords_include), limits.get("keywords", 12)
    )
    liked = _cap(pos_titles, limits.get("pos", 7))
    disliked = _cap(neg_titles, limits.get("neg", 5))

    parts: list[str] = []

    # header
    if query_text and query_text.strip():
        parts.append(
            "Here is the user’s request and taste signals, followed by the exact candidates to use.\n"
        )
        parts.append("**User Query:**")
        parts.append(query_text.strip() + "\n")
    else:
        parts.append(
            "Here is the user’s taste signals, followed by the exact candidates to use.\n"
        )

    # user signals
    parts.append("**User Signals:**")
    parts.append(f"- Selected Genres: {_csv(genres)}")
    parts.append(f"- Selected Keywords: {_csv(keywords)}")
    parts.append(f"- Liked Titles: {_csv(liked)} ")
    parts.append(f"- Disliked Titles: {_csv(disliked)}")
    parts.append("")

    # candidates
    parts.append("**Candidates (use all, in this order):**")
    parts.append(
        "Each block below contains the full context for one title. Do not combine fields across titles.\n"
    )

    for idx, c in enumerate(candidates[:batch_size], start=1):
        media_id = f"Media ID: {((c.payload or {}).get('media_id', ''))}"
        ctx = _sanitize_code_block(
            str((c.payload or {}).get("embedding_text", "")).strip()
        )
        # Guardrail: empty context → still emit fenced empty block to preserve count/order
        parts.append("```")
        parts.append(media_id)
        parts.append(ctx)
        parts.append("```")
        # (No extra blank line; streaming parsers often prefer tight blocks)

    # explicit instructions (verbatim from template expectations)
    parts.append("\n**Instructions:**")
    parts.append(
        f"- Output {batch_size} recommendation lines using the specified format."
    )
    parts.append(
        "- For each candidate, you may reference the user's liked and disliked titles as evidence, "
        "but you must never say the user will like a title because they already like the exact same title."
    )

    return "\n".join(parts)


# == User prompt builder for interactive recommendation mode ==
def format_rec_context(candidates: list):
    context = "\n\n".join([c.payload.get("llm_context", "") for c in candidates])
    return context


def build_interactive_user_prompt(
    *, candidates: list, query_text: str, user_signals: UserSignals | None = None
):
    context = format_rec_context(candidates=candidates)
    user_message = f"Here is the user query: {query_text}\n\nHere are the candidate items:\n{context}"
    return user_message
