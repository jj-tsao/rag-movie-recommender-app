from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math
from app.ranking.types import Candidate

@dataclass(frozen=True)
class NormAnchors:
    rating_floor: float
    rating_ceil: float
    pop_anchor: float  # used with log1p

# Module-level defaults
DEFAULT_ANCHORS: Dict[str, NormAnchors] = {
    "movie": NormAnchors(rating_floor=6.0, rating_ceil=9.0, pop_anchor=31.0),   # pop_anchor = ~P99(27)*1.15
    "tv":    NormAnchors(rating_floor=7.0, rating_ceil=9.0, pop_anchor=58.0),  # pop_anchor = ~P99(50)*1.15
}

def set_metadata_anchors(media_type: str, anchors: NormAnchors) -> None:
    """Runtime override (feature flag, admin panel, tests)."""
    DEFAULT_ANCHORS[media_type.lower()] = anchors

def _clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else 1.0 if x >= 1.0 else x

def norm_rating(x: Optional[float], floor_: float, ceil_: float) -> float:
    if x is None:
        return 0.0
    return _clamp01((float(x) - floor_) / max(1e-6, (ceil_ - floor_)))

def norm_popularity(pop: float, anchor: float, alpha: float = 0.6) -> float:
    if pop is None:
        return 0.0
    return (math.log1p(pop) / math.log1p(anchor)) ** alpha

def metadata_rerank(
    candidates: List[Candidate],
    *,
    weights: Dict[str, float] = dict(dense=0.60, sparse=0.10, rating=0.20, popularity=0.10),
    media_type: str,
    anchors: Optional[NormAnchors] = None,
) -> List[Tuple[Candidate, float]]:
    mt = media_type.lower()
    a = anchors or DEFAULT_ANCHORS.get(mt, DEFAULT_ANCHORS["movie"])
    
    s_vals = sorted([float(c.sparse_score) for c in candidates if c.sparse_score and c.sparse_score > 0.0])
    p95 = s_vals[int(0.95 * (len(s_vals) - 1))] if s_vals else 1e-6
    den = math.log1p(p95)
    
    out: List[Tuple[Candidate, float]] = []
    for c in candidates:
        r = norm_rating(c.payload.get("vote_average"), a.rating_floor, a.rating_ceil)
        p = norm_popularity(c.payload.get("popularity"), a.pop_anchor)
        dense  = float(c.dense_score  or 0.0)
        raw_s = float(c.sparse_score or 0.0)
        sparse = _clamp01(math.log1p(max(0.0, raw_s)) / max(1e-6, den))
        score = (
            weights["dense"]       * dense +
            weights["sparse"]      * sparse +
            weights["rating"]      * r +
            weights["popularity"]  * p
        )
        out.append((c, score))

    out.sort(key=lambda t: t[1], reverse=True)
    return out
