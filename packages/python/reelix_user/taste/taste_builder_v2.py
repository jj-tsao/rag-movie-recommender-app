from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from reelix_core.types import BuildParams, MediaId, UserSignals
from reelix_user.signals.weights import compute_item_weights

Embed = np.ndarray


# ---- small utils ----
# L2 normalization
def _l2(x: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(x))
    return x if n == 0 else x / n


# weighted average vectors
def _wmean(vecs: list[np.ndarray], w: list[float]) -> np.ndarray:
    if not vecs:
        return np.zeros((0,), dtype=np.float32)
    acc = np.zeros_like(vecs[0], dtype=np.float32)
    s = float(sum(w) or 1.0)
    for v, ww in zip(vecs, w):
        acc += v * ww
    return acc / s


# ---- priors ----
def get_priors(
    keys: list[str], centroids: Mapping[str, np.ndarray], dim: int
) -> np.ndarray:
    picks: list[np.ndarray] = []
    for k in keys:
        v = centroids.get(k)
        if v is not None:
            picks.append(np.asarray(v, dtype=np.float32))
    if not picks:
        return np.zeros((dim,), dtype=np.float32)
    return _l2(np.mean(picks, axis=0).astype(np.float32))


# def prior_from_genres(genres: list[str], vibe_centroids: Mapping[str, np.ndarray], dim: int) -> np.ndarray:
#     picks: list[np.ndarray] = []
#     for g in genres:
#         v = vibe_centroids.get(g)
#         if v is not None:
#             picks.append(np.asarray(v, dtype=np.float32))
#     if not picks:
#         return np.zeros((dim,), dtype=np.float32)
#     return _l2(np.mean(picks, axis=0).astype(np.float32))

# def prior_from_keywords(keywords: list[str], embed_texts: Callable[[Sequence[str]], list[np.ndarray]], dim: int) -> np.ndarray:
#     if not keywords:
#         return np.zeros((dim,), dtype=np.float32)
#     q = ", ".join(keywords[:8])
#     [vec] = embed_texts([q])
#     return _l2(np.asarray(vec, dtype=np.float32))


# ---- main builder ----
def build_taste_vector(
    user: UserSignals,
    *,
    get_item_embeddings: Callable[[Sequence[MediaId]], Mapping[MediaId, Embed]],
    vibe_centroids: Mapping[str, Embed],
    keyword_centroids: Mapping[str, Embed],
    params: BuildParams,
    now: datetime | None = None,
) -> tuple[Embed, dict[str, Any]]:
    """
    Build a normalized taste vector:

    - Deduped by media_id.
    - For each title, merge rating + reactions into one weight.
    - Positive and negative titles contribute via separate centroids.
    - Genre/keyword priors mixed in with alpha/beta/gamma/delta.
    """
    now = now or datetime.now(timezone.utc)
    # 1) compute canonical weight per title
    weights = compute_item_weights(user.interactions, now, params)

    # 3) split by sign
    pos_ids = [mid for mid, w in weights.items() if w > 0]
    neg_ids = [mid for mid, w in weights.items() if w < 0]
    total = len(pos_ids) + len(neg_ids)

    # 4) fetch embeddings in one shot
    ids: list[MediaId] = pos_ids + neg_ids
    vec_map: Mapping[MediaId, Embed] = get_item_embeddings(ids) if ids else {}

    # 5) positive centroid (weights with decay)
    vpos_list: list[Embed] = []
    wpos: list[float] = []
    for mid in pos_ids:
        v = vec_map.get(mid)
        if v is None:
            continue
        vpos_list.append(np.asarray(v, dtype=np.float32))
        wpos.append(weights[mid])

    vpos = (
        _wmean(vpos_list, wpos)
        if vpos_list
        else np.zeros((params.dim,), dtype=np.float32)
    )

    # 6) negative centroid (use magnitude; sign handled later)
    vneg_list: list[Embed] = []
    wneg: list[float] = []
    for mid in neg_ids:
        v = vec_map.get(mid)
        if v is None:
            continue
        vneg_list.append(np.asarray(v, dtype=np.float32))
        wneg.append(abs(weights[mid]))

    vneg = (
        _wmean(vneg_list, wneg)
        if vneg_list
        else np.zeros((params.dim,), dtype=np.float32)
    )

    # 7) priors from genres/keywords (unchanged from your design)
    genre_vecs = [
        np.asarray(v, dtype=np.float32)
        for key, v in vibe_centroids.items()
        if getattr(user, "genres_include", None) and key in user.genres_include
    ]

    if genre_vecs:
        g_prior = np.mean(genre_vecs, axis=0)
    else:
        g_prior = np.zeros((params.dim,), dtype=np.float32)

    keyword_vecs = [
        np.asarray(v, dtype=np.float32)
        for key, v in keyword_centroids.items()
        if getattr(user, "keywords_include", None) and key in user.keywords_include
    ]

    if keyword_vecs:
        k_prior = np.mean(keyword_vecs, axis=0)
    else:
        k_prior = np.zeros((params.dim,), dtype=np.float32)

    # 8) combine
    combo = (
        params.alpha * vpos
        - params.beta * vneg
        + params.gamma * g_prior
        + params.delta * k_prior
    )

    # 9) cold start smoothing based on distinct titles, not raw events
    if (
        len(pos_ids) < params.min_pos_for_profile
        or total < params.min_total_for_profile
    ):
        combo = 0.5 * combo + 0.5 * (0.6 * g_prior + 0.4 * k_prior)

    # 10) normalize
    vec = _l2(combo).astype(np.float32)
    debug = {
        "pos_count": len(pos_ids),
        "neg_count": len(neg_ids),
        "vpos_norm": float(np.linalg.norm(vpos)),
        "vneg_norm": float(np.linalg.norm(vneg)),
        "g_prior_norm": float(np.linalg.norm(g_prior)),
        "k_prior_norm": float(np.linalg.norm(k_prior)),
        "params": vars(params),
    }
    return vec, debug
