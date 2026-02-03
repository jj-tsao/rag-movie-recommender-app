from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import re
import time
from reelix_core.types import UserTasteContext
from reelix_ranking.rrf import rrf
from reelix_ranking.metadata import metadata_rerank
from reelix_ranking.types import Candidate, ScoreTrace
from reelix_ranking.diversification import diversify_by_collection
from reelix_retrieval.base_retriever import BaseRetriever
from qdrant_client.models import Filter as QFilter
from concurrent.futures import ThreadPoolExecutor


def _normalize_title(title: str) -> str:
    """Normalize title for comparison (lowercase, no punctuation)."""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)  # Remove punctuation
    title = re.sub(r'\s+', ' ', title)     # Normalize whitespace
    return title.strip()


def _filter_mentioned_titles(
    candidates: List[Candidate],
    mentioned_titles: List[str],
) -> List[Candidate]:
    """Filter out candidates whose titles match mentioned_titles (case-insensitive)."""
    if not mentioned_titles:
        return candidates

    normalized_mentioned = {_normalize_title(t) for t in mentioned_titles}

    filtered = []
    for candidate in candidates:
        title = candidate.payload.get("title", "")
        if _normalize_title(title) not in normalized_mentioned:
            filtered.append(candidate)
        else:
            print(f"[Pipeline] Filtered mentioned title: {title}")

    return filtered


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
        media_type: str,
        dense_vec: List[float],
        sparse_vec: Dict[str, List[float]],
        query_text: str | None = None,
        qfilter: QFilter | None = None,
        user_context: UserTasteContext | None = None,
        # Tunable variables
        dense_depth: int = 300,
        sparse_depth: int = 20,
        meta_top_n: int = 100,
        ce_rerank: bool = False,
        meta_ce_top_n: int = 30,
        weights: Dict[str, float] = dict(
            dense=0.60, sparse=0.10, rating=0.20, popularity=0.10, genre=0.00
        ),
        final_top_k: int = 20,
        mentioned_titles: List[str] | None = None,
    ) -> Tuple[List[Candidate], Dict[int, ScoreTrace]]:
        total_start = time.perf_counter()
        # 1) retrieve - parallelize Qdrant searches to reduce network latency
        retrieval_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_dense = ex.submit(
                self.ret.dense,
                dense_vec,
                media_type,
                qfilter,
                dense_depth,
            )
            f_sparse = ex.submit(
                self.ret.sparse, sparse_vec, media_type, qfilter, sparse_depth
            )
            dense = f_dense.result()
            sparse = f_sparse.result()
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
        print(f"[timing] recommend_retrieval_ms={retrieval_ms:.1f}")

        dense_ids = [c.id for c in dense]
        sparse_ids = [c.id for c in sparse]

        # 2) base RRF pool (ids only)
        pool_ids = {i for i, _ in rrf([dense_ids, sparse_ids], k=self.rrf_k)}

        # 3) merge both lists, keeping both scores
        from reelix_retrieval.pooling import merge_by_id

        pool = merge_by_id(dense, sparse, pool_ids)

        # 3.5) Filter mentioned titles before reranking
        if mentioned_titles:
            pool = _filter_mentioned_titles(pool, mentioned_titles)
            print(f"[Pipeline] After filtering mentioned titles: {len(pool)} candidates")

        # 4) metadata rerank
        meta_start = time.perf_counter()
        meta_scored = metadata_rerank(
            candidates=pool,
            media_type=media_type,
            user_context=user_context,
            weights=weights,
        )
        meta_ms = (time.perf_counter() - meta_start) * 1000
        print(f"[timing] recommend_metadata_ms={meta_ms:.1f}")
        meta_sorted = [c for c, m_score, m_trace in meta_scored][:meta_top_n]
        diversify_start = time.perf_counter()
        meta_sorted, _ = diversify_by_collection(
            meta_sorted,
            per_collection_cap=1,
        )
        diversify_ms = (time.perf_counter() - diversify_start) * 1000
        print(f"[timing] recommend_diversify_ms={diversify_ms:.1f}")
        
        meta_top_ids = [c.id for c in meta_sorted[:meta_ce_top_n]]

        dense_rank_map = {cid: r for r, cid in enumerate(dense_ids, start=1)}
        sparse_rank_map = {cid: r for r, cid in enumerate(sparse_ids, start=1)}

        meta_score_map = {c.id: s for (c, s, t) in meta_scored}
        meta_breakdown_map = {c.id: t for (c, _, t) in meta_scored}

        traces: Dict[int, ScoreTrace] = {}

        # 4.5) Fallback to metadata reranked results when CE reranker is not available
        if query_text is None or ce_rerank is False:
            final = meta_sorted[:final_top_k]

            # Build traces (no ce_score, use metadata score as final score)
            for c in final:
                traces[c.id] = ScoreTrace(
                    id=c.id,
                    dense_rank=dense_rank_map.get(c.id),
                    sparse_rank=sparse_rank_map.get(c.id),
                    dense_score=c.dense_score,
                    sparse_score=c.sparse_score,
                    meta_score=meta_score_map.get(c.id),
                    meta_breakdown=meta_breakdown_map.get(c.id),
                    ce_score=None,
                    final_score=meta_score_map.get(
                        c.id
                    ),  # Fallback to use metadata reranking score as the final score
                    weights_used=weights.copy(),
                    title=c.payload.get("title", ""),
                )
            total_ms = (time.perf_counter() - total_start) * 1000
            print(f"[timing] recommend_total_ms={total_ms:.1f}")
            return final, traces

        # 5) CE over dense top-K2
        ce_start = time.perf_counter()
        dense_top = dense[:meta_ce_top_n]
        if self.ce:
            docs = [(c.payload or {}).get("embedding_text") or "" for c in dense_top]
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
        ce_ms = (time.perf_counter() - ce_start) * 1000
        print(f"[timing] recommend_ce_ms={ce_ms:.1f}")

        # 6) final fusion
        fusion_start = time.perf_counter()
        final_rrf = rrf([meta_top_ids, ce_order], k=self.rrf_k)
        final_ids = [i for i, _ in final_rrf]

        # 7) assemble outputs + traces
        index = {c.id: c for c in pool}
        final = [index[i] for i in final_ids if i in index][:final_top_k]

        final_rrf_map = dict(final_rrf)

        for cid in final_ids:
            traces[cid] = ScoreTrace(
                id=cid,
                dense_rank=dense_rank_map.get(cid),
                sparse_rank=sparse_rank_map.get(cid),
                meta_score=meta_score_map.get(cid),
                meta_breakdown=meta_breakdown_map.get(cid),
                ce_score=ce_score_map.get(cid),
                final_score=final_rrf_map.get(cid),
            )
        fusion_ms = (time.perf_counter() - fusion_start) * 1000
        print(f"[timing] recommend_fusion_ms={fusion_ms:.1f}")
        total_ms = (time.perf_counter() - total_start) * 1000
        print(f"[timing] recommend_total_ms={total_ms:.1f}")
        return final, traces

    def summarize_ranking(self, ranking: List[Candidate], top_k: int = 20):
        for idx, r in enumerate(ranking[:top_k], start=1):
            print(
                f"#{idx}: Title: {r.payload['title']} | Dense Score: {r.dense_score} | Sparse Score: {r.sparse_score} | Rating: {r.payload['vote_average']} | Popularity: {r.payload['popularity']}"
            )
