from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, Dict


@dataclass
class Candidate:
    id: int
    payload: dict[str, Any]
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None


@dataclass
class ScoreTrace:
    id: int
    # Stage ranks (lower is better)
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    # Scalar / model scores
    meta_score: float | None = None
    meta_breakdown: ScoreBreakdown | None = None
    ce_score: float | None = None
    final_score: float | None = None
    weights_used: Dict[str, float] = field(default_factory=dict)
    title: str | None = None


@dataclass(frozen=True)
class FeatureContribution:
    feature: str  # "dense", "sparse", "rating", "popularity", "genre"
    value: float  # feature value (pre-weight, posr-normalization)
    weight: float  # weight used in this run
    contribution: float  # weight * value
    source: str | None = None # for rating: "imdb", "tmdb", etc.


@dataclass(frozen=True)
class ScoreBreakdown:
    features: Dict[str, FeatureContribution]  # keyed by feature name

    @property
    def total(self) -> float:
        return sum(fc.contribution for fc in self.features.values())
