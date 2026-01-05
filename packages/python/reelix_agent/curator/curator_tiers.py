from typing import Iterable, Literal
from reelix_ranking.types import Candidate

CuratorCategory = Literal["strong_match", "moderate_match", "no_match"]


def _classify_curator_category(item: dict) -> tuple[CuratorCategory, int]:
    """
    Classify a single curator evaluation item into buckets:
      - total_fit = genre_fit + tone_fit + structure_fit + theme_fit  (0–8)

    Heuristic:
      - strong_match:
          total_fit >= 7 AND genre_fit >= 1 AND tone_fit >= 1
      - moderate_match:
          total_fit between 4 and 6 (inclusive) AND genre_fit >= 1
      - no_match:
          everything else

    Returns:
      (category, total_fit)
    """
    genre_fit = int(item.get("genre_fit", 0) or 0)
    tone_fit = int(item.get("tone_fit", 0) or 0)
    structure_fit = int(item.get("structure_fit", 0) or 0)
    theme_fit = int(item.get("theme_fit", 0) or 0)

    total_fit = genre_fit + tone_fit + structure_fit + theme_fit

    # Strong: very high total fit, with at least some genre + tone alignment.
    if (genre_fit == 2 and tone_fit == 2) or (total_fit >= 5 and genre_fit >= 1):
        category = "strong_match"
    # elif (
    #     total_fit >= 4
    #     and genre_fit == 2
    # ):
    #     category = "strong_match"

    # Moderate: decent overall fit with at least some genre alignment.
    elif 3 <= total_fit <= 4 and genre_fit >= 1:
        category = "moderate_match"

    # Otherwise: treat as no_match.
    else:
        category = "no_match"

    return category, total_fit


def _build_curator_index(
    evaluation_results: Iterable[dict],
) -> dict[int, dict]:
    """
    Build an index keyed by media_id
    """
    index: dict[int, dict] = {}

    for item in evaluation_results:
        media_id = item.get("media_id")
        if media_id is None:
            continue

        # Normalize scores
        genre_fit = int(item.get("genre_fit", 0) or 0)
        tone_fit = int(item.get("tone_fit", 0) or 0)
        structure_fit = int(item.get("structure_fit", 0) or 0)
        theme_fit = int(item.get("theme_fit", 0) or 0)

        category, total_fit = _classify_curator_category(
            {
                "genre_fit": genre_fit,
                "tone_fit": tone_fit,
                "structure_fit": structure_fit,
                "theme_fit": theme_fit,
            }
        )

        index[int(media_id)] = {
            "category": category,
            "genre_fit": genre_fit,
            "tone_fit": tone_fit,
            "structure_fit": structure_fit,
            "theme_fit": theme_fit,
            "total_fit": total_fit,
        }

    return index


def apply_curator_tiers(
    *,
    evaluation_results: Iterable[dict],
    candidates: list[Candidate],
    limit: int = 8,
) -> tuple[list[Candidate], dict]:
    """
    Apply curator tiers to an already-ranked list of candidates.

    - Buckets each candidate into strong / moderate / no_match using
      the curator's dimension scores (genre/tone/structure/theme).
    - Preserves the original pipeline order **within** each bucket.
    - Then selects a final slate using your existing tier logic.
    """
    curator_index = _build_curator_index(evaluation_results)

    for c in candidates:
        print (c.payload.get("title"), curator_index.get(int(c.id)))

    strong_tier: list[Candidate] = []
    moderate_tier: list[Candidate] = []
    no_tier_ids: list[int] = []

    # Partition into tiers, preserving the original pipeline order
    for c in candidates:
        media_id = int(c.id)
        payload = c.payload or {}

        info = curator_index.get(media_id)
        if info is None:
            # If curator missed this id entirely, treat as moderate by default.
            category: CuratorCategory = "moderate_match"
            genre_fit = tone_fit = structure_fit = theme_fit = total_fit = 0
        else:
            category = info["category"]
            genre_fit = info["genre_fit"]
            tone_fit = info["tone_fit"]
            structure_fit = info["structure_fit"]
            theme_fit = info["theme_fit"]
            total_fit = info["total_fit"]

        # Stamp curator signals onto payload for downstream logging/UI
        payload["curator_category"] = category
        payload["curator_genre_fit"] = genre_fit
        payload["curator_tone_fit"] = tone_fit
        payload["curator_structure_fit"] = structure_fit
        payload["curator_theme_fit"] = theme_fit
        payload["curator_total_fit"] = total_fit
        c.payload = payload

        if category == "strong_match":
            strong_tier.append(c)
        elif category == "moderate_match":
            moderate_tier.append(c)
        else:  # "no_match"
            no_tier_ids.append(media_id)

    strong_count = len(strong_tier)
    moderate_count = len(moderate_tier)

    final_candidates: list[Candidate] = []

    # == Selection logic (unchanged semantics, just using new buckets) ==
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
        max_moderates = min(4, remaining, moderate_count)
        final_candidates.extend(moderate_tier[:max_moderates])

    # Case 5: 0 strongs -> moderates act as soft top tier (up to 5)
    else:  # strong_count == 0
        max_moderates = min(5, moderate_count, limit)
        final_candidates.extend(moderate_tier[:max_moderates])

    no_match_tier = [c for c in candidates if int(c.id) in no_tier_ids]

    stats = {
        "limit": limit,
        "total_candidates": len(candidates),
        "strong_count": strong_count,
        "moderate_count": moderate_count,
        "no_match_count": len(no_tier_ids),
        "no_match_ids": no_tier_ids,
        "served_count": len(final_candidates),
        # Some extra debug sugar if you want aggregates later:
        "strong_ids": [int(c.id) for c in strong_tier],
        "moderate_ids": [int(c.id) for c in moderate_tier],
    }

    print("strong_tier: ", [c.payload.get("title") for c in strong_tier])
    print("moderate_tier: ", [c.payload.get("title") for c in moderate_tier])
    print("no_match: ", [c.payload.get("title") for c in no_match_tier])
    print("final_candidates: ", [c.payload.get("title") for c in final_candidates])

    return final_candidates, stats