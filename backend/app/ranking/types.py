from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Candidate:
    id: str
    payload: Dict[str, Any]
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None


@dataclass
class ScoreTrace:
    id: str
    # Stage ranks (lower is better)
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    # Scalar / model scores
    meta_score: Optional[float] = None
    ce_score: Optional[float] = None
    final_rrf: Optional[float] = None
