from __future__ import annotations
from collections import defaultdict
from typing import List, Tuple


def rrf(rankings: List[List[str]], k: int = 60) -> List[Tuple[str, float]]:
    """
    Reciprocal Rank Fusion.
    rankings: list of ranked ID lists, e.g., [[id1,id2,...], [id3,id1,...]]
    Returns: sorted list of (id, score).
    """
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
