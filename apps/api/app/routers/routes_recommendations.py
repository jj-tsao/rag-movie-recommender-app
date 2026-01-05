import asyncio
from functools import partial

from anyio import from_thread
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from reelix_recommendation.orchestrator import orchestrate

from app.deps.deps import (
    get_chat_completion_llm,
    get_logger,
    get_recipe_registry,
    get_recommend_pipeline,
)
from app.deps.supabase_client import (
    get_current_user_id,
    get_user_context_service,
)
from app.schemas import FinalRecsRequest, InteractiveRequest

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

ENDPOINT = "recommendations/interactive"


@router.post("/interactive")
async def recommend_interactive(
    req: InteractiveRequest,
    batch_size: int = 20,
    user_id: str | None = Depends(get_current_user_id),
    registry=Depends(get_recipe_registry),
    user_context_svc=Depends(get_user_context_service),
    pipeline=Depends(get_recommend_pipeline),
    chat_llm=Depends(get_chat_completion_llm),
    logger=Depends(get_logger),
):
    recipe = registry.get(kind="interactive")
    user_context = await user_context_svc.fetch_user_taste_context(
        user_id, req.media_type
    )

    def gen():
        yield "[[MODE:recommendation]]\n"
        final_candidates, traces, ctx_log, llm_prompts = orchestrate(
            recipe=recipe,
            pipeline=pipeline,
            media_type=req.media_type.value,
            query_text=req.query_text,
            query_filter=req.query_filters,
            batch_size=batch_size,
            user_context=user_context,
        )

        meta = {
            "recipe": "interactive@v1",
            "items_brief": [
                {
                    "media_id": (c.payload or {}).get("media_id"),
                    "title": (c.payload or {}).get("title"),
                }
                for c in final_candidates
            ],
        }

        log_request = partial(
            logger.log_query_intake,
            endpoint=ENDPOINT,
            query_id=req.query_id,
            user_id=user_id,
            session_id=req.session_id,
            media_type=req.media_type,
            query_text=req.query_text,
            query_filters=req.query_filters,
            ctx_log=ctx_log,
            pipeline_version="RecommendPipeline@v2",
            batch_size=20,
            device_info=req.device_info,
            request_meta=meta,
        )

        log_results = partial(
            logger.log_candidates,
            endpoint=ENDPOINT,
            query_id=req.query_id,
            media_type=req.media_type,
            candidates=final_candidates,
            traces=traces,
            stage="prompt_context",
        )

        from_thread.run(log_request)
        from_thread.run(log_results)

        messages = llm_prompts.calls[0].messages
        for chunk in chat_llm.stream(
            messages=messages,
            temperature=0.7,
        ):
            yield chunk

    return StreamingResponse(gen(), media_type="text/plain")


@router.post("/log/final_recs")
async def log_final_recommendations(
    req: FinalRecsRequest,
    logger=Depends(get_logger),
):
    asyncio.create_task(
        logger.log_why(
            endpoint=ENDPOINT, query_id=req.query_id, final_recs=req.final_recs
        )
    )
