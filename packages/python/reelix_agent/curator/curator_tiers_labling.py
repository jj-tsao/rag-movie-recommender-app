from typing import Iterable, Literal
from reelix_ranking.types import Candidate

CuratorCategory = Literal["strong_match", "moderate_match", "no_match"]


def _build_curator_index(
    evaluation_results: Iterable[dict],
) -> dict[int, CuratorCategory]:
    index: dict[int, CuratorCategory] = {}

    for item in evaluation_results:
        media_id = item.get("media_id")
        category = item.get("match_category")
        if media_id is None or category not in (
            "strong_match",
            "moderate_match",
            "no_match",
        ):
            continue
        index[int(media_id)] = category  # normalize to int keys

    return index


def apply_curator_tiers(
    *,
    evaluation_results: Iterable[dict],
    candidates: list[Candidate],
    limit: int = 8,
) -> tuple[list[Candidate], dict]:
    curator_index = _build_curator_index(evaluation_results)
    
    print ("curator_index: ", curator_index)

    strong_tier: list[Candidate] = []
    moderate_tier: list[Candidate] = []
    no_tier_ids: list[int] = []

    # Partition into tiers, preserving the original pipeline order
    for c in candidates:
        media_id = c.id
        payload = c.payload or {}

        category: CuratorCategory = curator_index.get(
            int(media_id),
            "moderate_match",  # default if curator missed it
        )

        # Stamp the category onto the payload for downstream logging/UI
        payload["curator_category"] = category
        c.payload = payload

        if category == "strong_match":
            strong_tier.append(c)
        elif category == "moderate_match":
            moderate_tier.append(c)
        else:  # "no_match" or missing
            no_tier_ids.append(int(media_id))


    strong_count = len(strong_tier)
    moderate_count = len(moderate_tier)

    final_candidates: list[Candidate] = []

    # == Selection logic ==
    # Case 1: serve all strong matches when meet or exceed limit
    if strong_count >= limit:
        final_candidates = strong_tier[:limit]

    # Case 2: strongs are 5+ but less than limit -> only strongs, no moderates
    elif strong_count >= 5:
        final_candidates = strong_tier  # strong_count < limit, we don't top off

    # Case 3: 3–4 strongs -> strongs + up to 2 moderates (respect limit)
    elif 3 <= strong_count <= 4:
        final_candidates.extend(strong_tier)
        remaining = max(0, limit - len(final_candidates))
        max_moderates = min(2, remaining, moderate_count)
        final_candidates.extend(moderate_tier[:max_moderates])

    # Case 4: 1–2 strongs -> strongs + up to 4 moderates (respect limit)
    elif strong_count in (1, 2):
        final_candidates.extend(strong_tier)
        remaining = max(0, limit - len(final_candidates))
        # allow up to 4 moderates; no longer require moderates <= strongs
        max_moderates = min(4, remaining, moderate_count)
        final_candidates.extend(moderate_tier[:max_moderates])

    # Case 5: 0 strongs -> moderates act as soft top tier (up to 4)
    else:  # strong_count == 0
        max_moderates = min(4, moderate_count, limit)
        final_candidates.extend(moderate_tier[:max_moderates])

    stats = {
        "limit": limit,
        "total_candidates": len(candidates),
        "strong_count": len(strong_tier),
        "moderate_count": len(moderate_tier),
        "no_match_count": len(no_tier_ids),
        "no_match_ids": no_tier_ids,
        "served_count": len(final_candidates),
    }
    
    print ("strong_tier: ", [c.payload.get("title") for c in strong_tier])
    print ("moderate_tier: ", [c.payload.get("title") for c in moderate_tier])
    no_match_tier = [c for c in candidates if int(c.id) in no_tier_ids]
    print ("no_match: ", [c.payload.get("title") for c in no_match_tier])
    print ("final_candidates: ",[c.payload.get("title") for c in final_candidates])

    return final_candidates, stats
