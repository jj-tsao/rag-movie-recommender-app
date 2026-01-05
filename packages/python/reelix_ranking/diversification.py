from collections import defaultdict


def diversify_by_collection(
    candidates: list,  # list[Candidate] in descending meta score order
    *,
    per_collection_cap: int = 1,
) -> tuple[list, list[dict]]:
    counts = defaultdict(int)
    pruned = []

    def col_of(c):
        p = getattr(c, "payload", {}) or {}
        col = p.get("collection")
        # Fallback bucket so singletons don't get grouped
        return col or f"__solo__:{p.get('media_id', c.id)}"

    out = []
    for c in candidates:
        cid = c.id
        col = col_of(c)
        k = counts[col]  # 0-based index within this collection
        if per_collection_cap is not None and k >= per_collection_cap:
            pruned.append(
                {"media_id": cid, "collection": col, "title": c.payload.get("title")}
            )
            # Hard block
            continue
        out.append(c)
        counts[col] += 1

    return out, pruned
