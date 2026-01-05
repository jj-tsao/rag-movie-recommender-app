from reelix_core.types import MediaId

def select_titles_for_prompt(
    weights: dict[MediaId, float],
    K_pos: int = 7,
    K_neg: int = 2,
) -> tuple[list[MediaId], list[MediaId]]:
    # Top positives by descending weight (tie-break by media_id)
    pos_ids = [
        mid for mid, _ in sorted(
            ((mid, w) for mid, w in weights.items() if w > 0),
            key=lambda x: (x[1], x[0]),
            reverse=True,
        )[:K_pos]
    ]

    # Top negatives by descending magnitude (tie-break by media_id)
    neg_ids = [
        mid for mid, _ in sorted(
            ((mid, w) for mid, w in weights.items() if w < 0),
            key=lambda x: (abs(x[1]), x[0]),
            reverse=True,
        )[:K_neg]
    ]

    return pos_ids, neg_ids