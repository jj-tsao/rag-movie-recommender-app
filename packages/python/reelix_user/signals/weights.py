from datetime import datetime


from reelix_core.types import BuildParams, Interaction, MediaId

from .decay import tdecay
from .reducers import latest, map_reaction, group_by_media


def _rating_to_weight(r: float) -> float:
    """
    Map 1–10 star rating → [-0.8, 1.0] style range.
    """
    w = (r - 5.0) / 5.0  # 5 -> 0.0, 8 -> 0.6, 10 -> 1.0, 2 -> -0.6
    return max(-0.8, min(1.0, w))


def _compute_item_weight(
    interactions: list[Interaction],
    now: datetime,
    params: BuildParams,
) -> float:
    """
    Collapse all signals per (user, media_id) into a single signed weight.

    - If a rating exists:
        - Use rating as the primary anchor.
        - Only apply reaction if it occurs AFTER the rating.
            - love/like: gentle positive nudge
            - dislike: strong negative correction
    - If no rating:
        - Use reaction alone.
    - Apply recency decay based on the latest signal used.
    """

    # latest by type
    rating_ev = latest(interactions, {"rating"})
    reaction_ev = latest(interactions, {"love", "like", "dislike", "rec_reaction"})
    rx = map_reaction(reaction_ev) if reaction_ev else None
    watchl_add_ev = latest(interactions, {"add_to_watchlist"})
    watchl_rm_ev = latest(interactions, {"remove_from_watchlist"})

    base = 0.0
    used_signal = "none"

    # --- Case 1: rating exists -> anchor on rating ---
    if rating_ev is not None:
        rv = getattr(rating_ev, "value", None)
        if rv is not None:
            base = _rating_to_weight(float(rv))
            used_signal = "rating"

        # Only let reaction influence if it is strictly AFTER the rating
        if reaction_ev is not None and reaction_ev.ts > rating_ev.ts and rx is not None:
            if rx == "love":
                base += 0.5 * params.w_love  # gentle boost
            elif rx == "like":
                base += 0.5 * params.w_like  # smaller boost
            elif rx == "dislike":
                # stronger correction: treat as changed mind
                base -= max(0.5, 0.5 * params.w_dislike)
            used_signal = "rating_plus_reaction"

    # --- Case 2: no rating -> rely purely on reaction ---
    else:
        if rx == "love":
            base = params.w_love
            used_signal = "reaction"
        elif rx == "like":
            base = params.w_like
            used_signal = "reaction"
        elif rx == "dislike":
            base = -abs(params.w_dislike)
            used_signal = "reaction"

    # --- Case 3: no rating/reaction -> watchlist as soft positive ---
    if used_signal == "none" and watchl_add_ev is not None:
        # ensure it's not canceled by a later remove
        if watchl_rm_ev is None or watchl_add_ev.ts > watchl_rm_ev.ts:
            base = getattr(params, "w_watchlist", 0.25)
            used_signal = "watchlist"

    # No meaningful signal for this title
    if used_signal == "none" or base == 0.0:
        return 0.0

    # Clamp to a sane range
    if base > 1.2:
        base = 1.2
    elif base < -1.0:
        base = -1.0

    # Choose the timestamp of the signal that actually defines this weight
    if used_signal == "rating" and rating_ev is not None:
        latest_ts = rating_ev.ts
    elif (
        used_signal in ("reaction", "rating_plus_reaction") and reaction_ev is not None
    ):
        latest_ts = reaction_ev.ts
    elif used_signal == "watchlist" and watchl_add_ev is not None:
        latest_ts = watchl_add_ev.ts
    else:
        # Fallback: should basically never hit if used_signal is True, but safe
        latest_ts = max(it.ts for it in interactions)

    # Apply recency decay
    decay = tdecay(latest_ts, now, params.lambda_month)

    return base * decay


def compute_item_weights(
    interactions: list[Interaction],
    now: datetime,
    params: BuildParams,
) -> dict[MediaId, float]:
    by_media = group_by_media(interactions)
    weights: dict[MediaId, float] = {}
    for media_id, events in by_media.items():
        w = _compute_item_weight(events, now, params)
        if w != 0.0:
            weights[media_id] = w
    return weights
