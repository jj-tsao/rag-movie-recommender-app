from typing import Any
from reelix_recommendation.types import OrchestrationRecipe
from reelix_recommendation.recommend import RecommendPipeline
from reelix_core.types import UserTasteContext, QueryFilter, PromptsEnvelope
from reelix_ranking.types import Candidate, ScoreTrace


def orchestrate(
    *,
    recipe: OrchestrationRecipe,
    media_type: str,
    query_text: str | None = None,
    query_filter: QueryFilter | None = None,
    batch_size: int,
    user_id: str | None = None,
    user_context: UserTasteContext | None = None,
    pipeline: RecommendPipeline,
) -> tuple[list[Candidate], dict[int, ScoreTrace], dict[str, Any], PromptsEnvelope]:
    dense_vec, sparse_vec, qfilter = recipe.build_inputs(
        media_type=media_type,
        query_text=query_text,
        query_filter=query_filter,
        user_context=user_context,
    )

    params = recipe.pipeline_params()

    final, traces = pipeline.run(
        media_type=media_type,
        dense_vec=dense_vec,
        sparse_vec=sparse_vec,
        query_text=query_text,
        qfilter=qfilter,
        user_context=user_context,
        **params,
    )

    # server side debug print
    # pipeline.summarize_ranking(final)

    ctx_log = recipe.build_context_log(user_context)

    llm_prompts = recipe.build_prompt(
        query_text=query_text,
        batch_size=batch_size,
        user_context=user_context,
        candidates=final,
    )

    return final, traces, ctx_log, llm_prompts
