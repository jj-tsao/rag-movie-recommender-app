from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import datetime, timezone

from reelix_core.types import UserTasteContext
from reelix_ranking.types import Candidate, FeatureContribution, ScoreBreakdown


@dataclass(frozen=True)
class NormAnchors:
    rating_floor: float
    rating_ceil: float
    pop_anchor: float  # used with log1p
    recency_half_life_years: float = 4.0


# Module-level defaults
DEFAULT_ANCHORS: Dict[str, NormAnchors] = {
    "movie": NormAnchors(
        rating_floor=6.0, rating_ceil=9.0, pop_anchor=31.0, recency_half_life_years=4.0
    ),  # pop_anchor = ~P99(27)*1.15
    "tv": NormAnchors(
        rating_floor=7.0, rating_ceil=9.0, pop_anchor=58.0, recency_half_life_years=2.0
    ),  # pop_anchor = ~P99(50)*1.15
}


def set_metadata_anchors(media_type: str, anchors: NormAnchors) -> None:
    """Runtime override (feature flag, admin panel, tests)."""
    DEFAULT_ANCHORS[media_type.lower()] = anchors


def _clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else 1.0 if x >= 1.0 else x


def select_rating_source(payload: dict) -> tuple[float | None, float | None, str]:
    """
    Prefer IMDb; fall back to TMDB.
    Returns (avg_rating, num_votes, source_tag).
    """
    imdb_rating = payload.get("imdb_rating")
    imdb_votes = payload.get("imdb_votes")
    tmdb_rating = payload.get("vote_average")
    tmdb_votes = payload.get("vote_count")

    # Heuristic: prefer IMDb when it has at least some votes
    if imdb_rating is not None and imdb_votes is not None and imdb_votes > 0:
        return float(imdb_rating), float(imdb_votes), "imdb"

    # Fallback to TMDB if IMDb missing/empty
    if tmdb_rating is not None and tmdb_votes is not None and tmdb_votes > 0:
        return float(tmdb_rating), float(tmdb_votes), "tmdb"

    # Very weak edge case fallbacks (rating but no votes, etc.)
    if imdb_rating is not None:
        return float(imdb_rating), float(imdb_votes or 0), "imdb_partial"
    if tmdb_rating is not None:
        return float(tmdb_rating), float(tmdb_votes or 0), "tmdb_partial"

    return None, None, "none"


def bayes_quality(avg, cnt, mu:float=7.2, m:float =5000.0):
    avg = float(avg or 0.0)
    cnt = float(cnt or 0.0)
    return (mu * m + avg * cnt) / (m + cnt)


def norm_rating(x: float | None, floor_: float, ceil_: float) -> float:
    if x is None:
        return 0.0
    return _clamp01((float(x) - floor_) / max(1e-6, (ceil_ - floor_)))


def norm_popularity(pop, anchor: float, alpha: float = 0.6) -> float:
    if pop is None:
        return 0.0
    return (math.log1p(pop) / math.log1p(anchor)) ** alpha


def genre_boost(user_genres: set[str], item_genres: set[str]) -> float:
    if not user_genres or not item_genres:
        return 0.0

    inter = len(user_genres & item_genres)
    total_user_pref = len(user_genres)

    # Only rewards matches, no punish to non-overlapping genres since user_genres are cold start interests in first_rec
    return inter / total_user_pref


def _parse_release_date_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Accept "YYYY-MM-DD" or full ISO. If 'Z' present, normalize to +00:00.
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        # If date-only, make it midnight UTC to avoid tz drift.
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return datetime.fromisoformat(s + "T00:00:00+00:00")
        return datetime.fromisoformat(s if "+" in s else s + "+00:00")
    except Exception:
        return None


def age_years_from_release_date(payload: dict) -> float | None:
    rd = _parse_release_date_iso(payload.get("release_date"))
    if not rd:
        return None
    now = datetime.now(timezone.utc)
    delta_days = max(0, (now - rd).days)
    return delta_days / 365.0


def norm_recency(age_years: float | None, half_life_years: float) -> float:
    if age_years is None:
        return 0.0
    # Exponential decay with half-life
    import math

    return _clamp01(math.exp(-math.log(2) * (age_years / max(1e-6, half_life_years))))


def freshness_bonus_days(payload: dict) -> float:
    """Optional gentle bump for very new titles; keep small to avoid runaway 'new & hyped' bias."""
    rd = _parse_release_date_iso(payload.get("release_date"))
    if not rd:
        return 0.0
    days = max(0, (datetime.now(timezone.utc) - rd).days)
    if days < 30:
        # cap early items at ~0.85 instead of 1.0; smoothly fade the bump over first month
        return 0.05 * (1.0 - days / 30.0)
    if days < 90:
        return 0.05 * (1.0 - (days - 30.0) / 60.0)
    return 0.0


def metadata_rerank(
    *,
    candidates: List[Candidate],
    media_type: str,
    user_context: UserTasteContext | None = None,
    weights: Dict[str, float] = dict(
        dense=0.60, sparse=0.10, rating=0.20, popularity=0.10, genre=0
    ),
    anchors: NormAnchors | None = None,
) -> List[Tuple[Candidate, float, ScoreBreakdown]]:
    mt = media_type.lower()
    a = anchors or DEFAULT_ANCHORS.get(mt, DEFAULT_ANCHORS["movie"])

    s_vals = sorted(
        [
            float(c.sparse_score)
            for c in candidates
            if c.sparse_score and c.sparse_score > 0.0
        ]
    )
    p95 = s_vals[int(0.95 * (len(s_vals) - 1))] if s_vals else 1e-6
    den = math.log1p(p95)
    user_genres = user_context.signals.genres_include if user_context else []

    out: List[Tuple[Candidate, float, ScoreBreakdown]] = []
    for c in candidates:
        # Dense + sparese scores
        dense = float(c.dense_score or 0.0)
        raw_s = float(c.sparse_score or 0.0)
        sparse = _clamp01(math.log1p(max(0.0, raw_s)) / max(1e-6, den))
        
        payload = c.payload or {}
        
        # Quality score (IMDB rating + votes, TMDB fallback)
        r_avg, r_cnt, rating_src = select_rating_source(payload)
        
        if rating_src.startswith("imdb"):
            # Slightly stronger priors: IMDb tends to have more votes
            mu, m = 7.2, 5000.0
        elif rating_src.startswith("tmdb"):
            mu, m = 7.0, 2000.0
        else:
            mu, m = 7.2, 5000.0

        raw_r = bayes_quality(r_avg, r_cnt, mu=mu, m=m)
        q = norm_rating(raw_r, a.rating_floor, a.rating_ceil)        

        # Popularity score (TMDB)
        p = norm_popularity(payload.get("popularity"), a.pop_anchor)
        c_genres = payload.get("genres")
        g = (
            genre_boost(set(user_genres), set(c_genres))
            if c_genres and user_genres
            else 0
        )

        # Recency score
        age_y = age_years_from_release_date(payload)
        rcy = norm_recency(
            age_y, a.recency_half_life_years
        )  + freshness_bonus_days(payload)

        feats: Dict[str, FeatureContribution] = {
            "dense": FeatureContribution(
                feature="dense",
                value=dense,
                weight=float(weights.get("dense", 0.0)),
                contribution=float(weights.get("dense", 0.0)) * dense,
            ),
            "sparse": FeatureContribution(
                feature="sparse",
                value=sparse,
                weight=float(weights.get("sparse", 0.0)),
                contribution=float(weights.get("sparse", 0.0)) * sparse,
            ),
            "rating": FeatureContribution(
                feature="rating",
                value=q,
                weight=float(weights.get("rating", 0.0)),
                contribution=float(weights.get("rating", 0.0)) * q,
                source=rating_src,
            ),
            "popularity": FeatureContribution(
                feature="popularity",
                value=p,
                weight=float(weights.get("popularity", 0.0)),
                contribution=float(weights.get("popularity", 0.0)) * p,
                source="tmdb",
            ),
            "genre": FeatureContribution(
                feature="genre",
                value=g,
                weight=float(weights.get("genre", 0.0)),
                contribution=float(weights.get("genre", 0.0)) * g,
            ),
            "recency": FeatureContribution(
                feature="recency",
                value=rcy,
                weight=float(weights.get("recency", 0.0)),
                contribution=float(weights.get("recency", 0.0)) * rcy,
            ),
        }

        breakdown = ScoreBreakdown(features=feats)
        score = breakdown.total

        out.append((c, score, breakdown))

    out.sort(key=lambda t: t[1], reverse=True)

    return out
