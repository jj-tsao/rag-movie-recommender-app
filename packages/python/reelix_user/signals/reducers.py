from collections import defaultdict
from typing import Any

from reelix_core.types import Interaction, MediaId


def latest(interactions: list[Any], kinds: set[str]) -> Any | None:
    """Return latest event whose kind is in kinds."""
    cand = [it for it in interactions if getattr(it, "kind", None) in kinds]
    if not cand:
        return None
    # prefer newest; tie-breaker with id if present (for determinism)
    return max(cand, key=lambda it: (it.ts, getattr(it, "id", "")))


def map_reaction(it: Any) -> str | None:
    """
    Normalize reaction-style events into 'love' / 'like' / 'dislike'.
    Supports:
    - kind == 'rec_reaction' with type
    - [legacy] kind already in {'love','like','dislike'}
    """
    if it is None:
        return None

    kind = getattr(it, "kind", None)
    if kind in ("love", "like", "dislike"):
        return kind

    if kind == "rec_reaction":
        v = getattr(it, "reaction", None)
        if v is None:
            return None
        else:
            return v


def group_by_media(
    interactions: list[Interaction],
) -> dict[MediaId, list[Any]]:
    by_media: dict[MediaId, list[Any]] = defaultdict(list)
    for it in interactions:
        # assume interactions have .media_id
        by_media[it.media_id].append(it)
    return by_media
