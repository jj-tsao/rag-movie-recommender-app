from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from app.ranking.rrf import rrf
from app.ranking.metadata import metadata_rerank
from app.ranking.types import Candidate, ScoreTrace
from app.retrieval.base_retriever import BaseRetriever
from app.retrieval.filter_builder import build_qfilter
from concurrent.futures import ThreadPoolExecutor


class RecommendPipeline:
    """
    4-stage orchestration:
      1) Base Fusion (RRF) over dense_depth and sparse_depth to form a pool
      2) Metadata rerank over pool -> meta_top_n
      3) Cross-Encoder rerank over dense ce_top_n
      4) Final Fusion (RRF) over (meta meta_ce_top_n) vs (CE meta_ce_top_n). Return Final Fusion final_top_k
    """

    def __init__(self, retriever: BaseRetriever, ce_model=None, *, rrf_k: int = 60):
        self.ret = retriever
        self.ce = ce_model
        self.rrf_k = rrf_k

    def run(
        self,
        *,
        query_text: str,
        dense_vec: List[float],
        sparse_vec: Dict[str, List[float]],
        media_type: str,
        genres: Optional[List[str]] = None,
        providers: Optional[List[str]] = None,
        year_range: Optional[Tuple[int, int]] = None,
        # Tunable variables
        dense_depth: int = 300,
        sparse_depth: int = 20,
        meta_top_n: int = 100,
        meta_ce_top_n: int = 30,
        weights: Dict[str, float] = dict(
            dense=0.60, sparse=0.10, rating=0.20, popularity=0.10
        ),
        final_top_k: int = 20,
    ) -> Tuple[List[Candidate], Dict[str, ScoreTrace]]:
        # 1) retrieve
        qfilter = build_qfilter(
            genres=genres, providers=providers, year_range=year_range
        )
        # Parallelize Qdrant searches to reduce network latency
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_dense = ex.submit(self.ret.dense, dense_vec, media_type, qfilter, dense_depth)
            f_sparse = ex.submit(self.ret.sparse, sparse_vec, media_type, qfilter, sparse_depth)
            dense = f_dense.result()
            sparse = f_sparse.result()

        dense_ids = [c.id for c in dense]
        sparse_ids = [c.id for c in sparse]

        # 2) base RRF pool (ids only)
        pool_ids = {i for i, _ in rrf([dense_ids, sparse_ids], k=self.rrf_k)}

        # 3) merge both lists, keeping both scores
        from app.retrieval.pooling import merge_by_id

        pool = merge_by_id(dense, sparse, pool_ids)

        # 4) metadata rerank
        meta_scored = metadata_rerank(
            pool,
            weights=weights,
            media_type=media_type,
        )
        meta_sorted = [c for c, _ in meta_scored][:meta_top_n]
        meta_top_ids = [c.id for c in meta_sorted[:meta_ce_top_n]]
        
        # 4.5) Fallback to metadata reranked results when CE reranker is not available
        if (self.ce is None):
            final = meta_sorted[:final_top_k]

            # Build traces (no ce_score, use metadata score as final score)
            traces: Dict[str, ScoreTrace] = {}
            dense_rank_map = {cid: r for r, cid in enumerate(dense_ids, start=1)}
            sparse_rank_map = {cid: r for r, cid in enumerate(sparse_ids, start=1)}
            meta_score_map = {c.id: s for (c, s) in meta_scored}

            for c in final:
                traces[c.id] = ScoreTrace(
                    id=c.id,
                    dense_rank=dense_rank_map.get(c.id),
                    sparse_rank=sparse_rank_map.get(c.id),
                    meta_score=meta_score_map.get(c.id),
                    ce_score=None,
                    final_rrf=meta_score_map.get(c.id),  # Fallback to use metadata reranking score as the final score
                )
            return final, traces


        # 5) CE over dense top-K2
        dense_top = dense[:meta_ce_top_n]
        if self.ce:
            docs = [c.payload.get("embedding_text") or "" for c in dense_top]
            ce_scores = self.ce.score(query_text, docs)
            ce_order = [
                cid
                for cid, _ in sorted(
                    zip([c.id for c in dense_top], ce_scores),
                    key=lambda t: t[1],
                    reverse=True,
                )
            ]
            ce_score_map = {
                cid: s for cid, s in zip([c.id for c in dense_top], ce_scores)
            }
        else:
            ce_order = [c.id for c in dense_top]
            ce_score_map = {}

        # 6) final fusion
        final_rrf = rrf([meta_top_ids, ce_order], k=self.rrf_k)
        final_ids = [i for i, _ in final_rrf]

        # 7) assemble outputs + traces
        index = {c.id: c for c in pool}
        final = [index[i] for i in final_ids if i in index][:final_top_k]

        traces: Dict[str, ScoreTrace] = {}
        dense_rank_map = {cid: r for r, cid in enumerate(dense_ids, start=1)}
        sparse_rank_map = {cid: r for r, cid in enumerate(sparse_ids, start=1)}
        meta_score_map = {c.id: s for (c, s) in meta_scored}
        final_rrf_map = dict(final_rrf)

        for cid in final_ids:
            traces[cid] = ScoreTrace(
                id=cid,
                dense_rank=dense_rank_map.get(cid),
                sparse_rank=sparse_rank_map.get(cid),
                meta_score=meta_score_map.get(cid),
                ce_score=ce_score_map.get(cid),
                final_rrf=final_rrf_map.get(cid),
            )
        return final, traces
