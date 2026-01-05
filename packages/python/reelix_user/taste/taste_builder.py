from __future__ import annotations
import math
from datetime import datetime, timezone
from typing import Callable, Sequence, Mapping, Any, Iterable
import numpy as np

from reelix_core.types import UserSignals, BuildParams, MediaId

Embed = np.ndarray

# ---- small utils ----

# L2 normalization
def _l2(x: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(x))
    return x if n == 0 else x / n


def _dedupe_reactions_by_media(interactions: Iterable[Any]) -> list[Any]:
    """
    For each media_id, keep a single reaction:
    - Only consider love/like/dislike.
    - Prefer more recent ts.
    - If same ts, prefer stronger reaction (love > like > dislike).
    """
    best: dict[MediaId, Any] = {}
    for it in interactions:
        if it.kind not in ("love", "like", "dislike"):
            continue
        prev = best.get(it.media_id)
        if prev is None:
            best[it.media_id] = it
            continue

        if it.ts > prev.ts:
            best[it.media_id] = it

    return list(best.values())


# weighted average vectors
def _wmean(vecs: list[np.ndarray], w: list[float]) -> np.ndarray:
    if not vecs:
        return np.zeros((0,), dtype=np.float32)
    acc = np.zeros_like(vecs[0], dtype=np.float32)
    s = float(sum(w) or 1.0)
    for v, ww in zip(vecs, w):
        acc += v * ww
    return acc / s


# absolute day difference
def _days(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 86400.0


# classic exponential decay per 30 days
def _tdecay(ts: datetime, now: datetime, lam_month: float) -> float:
    return math.exp(-lam_month * (_days(ts, now) / 30.0))


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
    get_item_embeddings: Callable[[Sequence[MediaId]], Mapping[MediaId, np.ndarray]],
    # embed_texts: Callable[[Sequence[str]], list[np.ndarray]],
    vibe_centroids: Mapping[str, np.ndarray],
    keyword_centroids: Mapping[str, np.ndarray],
    params: BuildParams,
    now: datetime | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    now = now or datetime.now(timezone.utc)

    dedup = _dedupe_reactions_by_media(user.interactions)

    pos = [it for it in dedup if it.kind in ("love", "like")]
    neg = [it for it in dedup if it.kind == "dislike"]
    total = len(pos) + len(neg)

    # fetch vectors
    ids = [it.media_id for it in pos] + [it.media_id for it in neg]
    vec_map = get_item_embeddings(ids) if ids else {}  # Dict[media_id, vector]

    # construct list of vectors and weights
    vpos_list, wpos = [], []
    for it in pos:
        v = vec_map.get(it.media_id)
        if v is None:
            continue
        base = params.w_love if it.kind == "love" else params.w_like
        wpos.append(
            base * _tdecay(it.ts, now, params.lambda_month)
        )  # default: half-life = 12 months
        vpos_list.append(np.asarray(v, dtype=np.float32))
    vneg_list, wneg = [], []
    for it in neg:
        v = vec_map.get(it.media_id)
        if v is None:
            continue
        wneg.append(params.w_dislike * _tdecay(it.ts, now, params.lambda_month))
        vneg_list.append(np.asarray(v, dtype=np.float32))

    vpos = (
        _wmean(vpos_list, wpos)
        if vpos_list
        else np.zeros((params.dim,), dtype=np.float32)
    )
    vneg = (
        _wmean(vneg_list, wneg)
        if vneg_list
        else np.zeros((params.dim,), dtype=np.float32)
    )

    # genre and keywor priors
    # g_prior = prior_from_genres(user.genres_include, vibe_centroids, params.dim) if user.genres_include else np.zeros((params.dim,), dtype=np.float32)
    # k_prior = prior_from_keywords(user.keywords_include, embed_texts, params.dim) if user.keywords_include else np.zeros((params.dim,), dtype=np.float32)
    g_prior = (
        get_priors(user.genres_include, vibe_centroids, params.dim)
        if user.genres_include
        else np.zeros((params.dim,), dtype=np.float32)
    )
    k_prior = (
        get_priors(user.keywords_include, keyword_centroids, params.dim)
        if user.keywords_include
        else np.zeros((params.dim,), dtype=np.float32)
    )

    combo = (
        params.alpha * vpos
        - params.beta * vneg
        + params.gamma * g_prior
        + params.delta * k_prior
    )

    # cold-start shaping
    if len(pos) < params.min_pos_for_profile or total < params.min_total_for_profile:
        combo = 0.5 * combo + 0.5 * (0.6 * g_prior + 0.4 * k_prior)

    vec = _l2(combo).astype(np.float32)
    debug = {
        "pos_count": len(pos),
        "neg_count": len(neg),
        "vpos_norm": float(np.linalg.norm(vpos)),
        "vneg_norm": float(np.linalg.norm(vneg)),
        "g_prior_norm": float(np.linalg.norm(g_prior)),
        "k_prior_norm": float(np.linalg.norm(k_prior)),
        "params": vars(params),
    }
    return vec, debug
