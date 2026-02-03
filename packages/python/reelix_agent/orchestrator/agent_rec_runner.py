from typing import Any, Iterable
import time
from datetime import datetime

from reelix_agent.core.types import RecQuerySpec
from reelix_core.types import UserTasteContext
from reelix_ranking.types import Candidate, ScoreTrace
from reelix_recommendation.recommend import RecommendPipeline
from reelix_retrieval.qdrant_filter import build_qfilter, provider_ids_from_names
from reelix_retrieval.query_encoder import Encoder as QueryEncoder

def _safe_final_score(t: ScoreTrace | None) -> float:
    if t is None or t.final_score is None:
        return float("-inf")
    return float(t.final_score)


class AgentRecRunner:
    """
    Adapter used by the Recommendation Agent to run the rec pipeline
    from a RecQuerySpec + user_context.
    """

    def __init__(
        self,
        pipeline: RecommendPipeline,
        query_encoder: QueryEncoder,
        # optional: weights, defaults, config, logger, etc.
    ) -> None:
        self._pipeline = pipeline
        self._query_encoder = query_encoder

    def run_for_agent(
        self,
        *,
        user_context: UserTasteContext | None,
        spec: RecQuerySpec,
        seen_media_ids: list[int] | None = None,
        turn_kind: str | None = None,
    ) -> tuple[list[Candidate], dict[int, ScoreTrace], dict[str, Any]]:
        """
        Map RecQuerySpec + user_context into:
          - dense_vec
          - sparse_vec
          - qfilter
        then call pipeline.run(...), and return:
          (candidates, traces, ctx_log, meta)
        """
        # 1) Build dense/sparse vectors from spec
        encode_start = time.perf_counter()
        dense_vec, sparse_vec = self._query_encoder.dense_and_sparse(
            text=spec.query_text, media_type=spec.media_type
        )
        encode_ms = (time.perf_counter() - encode_start) * 1000
        print(f"[timing] query_encode_ms={encode_ms:.1f}")

        # 2) Build filters (providers, genres, runtime, etc.)
        filter_start = time.perf_counter()
        qfilter = self._build_filters(
            user_context=user_context,
            spec=spec,
            # exclude_media_ids=exclude_media_ids,
        )
        filter_ms = (time.perf_counter() - filter_start) * 1000
        print(f"[timing] qfilter_ms={filter_ms:.1f}")

        # 3) Choose weights/top_k
        pipeline_params = self._build_pipeline_params(spec)

        # 4) Call pipeline
        candidates, traces = self._pipeline.run(
            media_type=spec.media_type.value,
            dense_vec=dense_vec,
            sparse_vec=sparse_vec,
            qfilter=qfilter,
            user_context=user_context,
            mentioned_titles=spec.seed_titles if spec.seed_titles else None,
            **pipeline_params,
        )

        if seen_media_ids and turn_kind == "refine":
            candidates, traces = self._apply_seen_penalty(
                candidates=candidates,
                traces=traces,
                seen_media_ids=seen_media_ids,
                multiplier=0.9,
            )

        # 5) Build context log

        ctx_log = self._build_context_log(user_context)

        return candidates, traces, ctx_log

    def _build_filters(
        self,
        *,
        user_context: UserTasteContext | None,
        spec: RecQuerySpec,
    ):
        providers = provider_ids_from_names(spec.providers) if spec.providers else None
        year_range = (1970, datetime.now().year) if spec.year_range is None else spec.year_range

        return build_qfilter(
            providers=providers,
            year_range=year_range,
        )

    def _build_pipeline_params(self, spec: RecQuerySpec) -> dict:
        return dict(
            final_top_k=12,
            weights=dict(
                dense=0.60, sparse=0.08, rating=0.20, popularity=0.08, genre=0.00, recency=0.04
            ),
        )

    def _apply_seen_penalty(
        self,
        *,
        candidates: list[Candidate],
        traces: dict[int, ScoreTrace],
        seen_media_ids: Iterable[int],
        multiplier: float = 0.95,
    ) -> tuple[list[Candidate], dict[int, ScoreTrace]]:
        """
        Apply novelty penalty by scaling ScoreTrace.final_score for seen IDs,
        then re-sort candidates by the updated final_score.

        Candidate stays unchanged (no need for Candidate.score/final_score).
        """
        seen = set(seen_media_ids)

        new_traces = dict(traces)
        for cid in seen:
            t = new_traces.get(cid)
            if t and t.final_score is not None:
                t.final_score *= multiplier

        new_candidates = sorted(
            candidates,
            key=lambda c: _safe_final_score(new_traces.get(c.id)),
            reverse=True,
        )
        return new_candidates, new_traces

    def _build_context_log(self, ctx: UserTasteContext | None) -> dict[str, Any]:
        if not ctx:
            return {}
        signals = getattr(ctx, "signals", None)
        genres = getattr(signals, "genres_include", []) if signals else []
        keywords = getattr(signals, "keywords_include", []) if signals else []

        return {
            "genres": genres,
            "keywords": keywords,
            "active_subs": getattr(ctx, "active_subscriptions", []),
            "subs_filter_mode": getattr(ctx, "provider_filter_mode", None),
        }
