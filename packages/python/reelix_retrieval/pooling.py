from __future__ import annotations
from typing import Dict, List
from reelix_ranking.types import Candidate


def merge_by_id(
    dense: List[Candidate], sparse: List[Candidate], keep_ids: set[int]
) -> List[Candidate]:
    by_id: Dict[int, Candidate] = {}
    for c in dense + sparse:
        if c.id not in keep_ids:
            continue
        if c.id in by_id:
            prev = by_id[c.id]
            if prev.dense_score is None and c.dense_score is not None:
                prev.dense_score = c.dense_score
            if prev.sparse_score is None and c.sparse_score is not None:
                prev.sparse_score = c.sparse_score
        else:
            by_id[c.id] = Candidate(
                id=c.id,
                payload=c.payload,
                dense_score=c.dense_score,
                sparse_score=c.sparse_score,
            )
    return list(by_id.values())
