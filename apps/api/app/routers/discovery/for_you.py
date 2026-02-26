"""
/discovery/for-you endpoints. Personalized feed based on user taste profile.
"""

import json
import time
import asyncio
import logging
import uuid
from typing import Iterator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from reelix_agent.core.types import PromptsEnvelope
from reelix_recommendation.orchestrator import orchestrate

from app.deps.deps import (
    get_recipe_registry,
    get_recommend_pipeline,
    get_logger,
)
from app.deps.deps_llm import get_chat_completion_llm
from app.deps.supabase_client import (
    get_current_user_id,
    get_user_context_service,
)
from app.deps.deps_redis_caches import get_ticket_store, get_why_cache
from app.infrastructure.cache.why_cache import WhyCache, CachedWhy
from app.infrastructure.cache.ticket_store import Ticket
from app.schemas import DiscoverRequest

from ._helpers import sse, pick_call

router = APIRouter(tags=["for-you"])

ENDPOINT = "discovery/for-you"
PIPELINE_VERSION = "RecommendPipeline@v2"
IDLE_TTL_SEC = 15 * 60
HEARTBEAT_SEC = 15
log = logging.getLogger(__name__)


@router.post("/for-you")
async def for_you(
    req: DiscoverRequest,
    batch_size: int = 8,
    user_id: str = Depends(get_current_user_id),
    registry=Depends(get_recipe_registry),
    user_context=Depends(get_user_context_service),
    pipeline=Depends(get_recommend_pipeline),
    store=Depends(get_ticket_store),
    logger=Depends(get_logger),
    why_cache: WhyCache = Depends(get_why_cache),
):
    """Get personalized recommendations based on user taste profile."""
    recipe = registry.get(kind="for_you_feed")
    user_context = await user_context.fetch_user_taste_context(user_id, req.media_type)

    final_candidates, traces, ctx_log, _ = orchestrate(
        recipe=recipe,
        pipeline=pipeline,
        media_type=req.media_type.value,
        query_filter=req.query_filters,
        batch_size=batch_size,
        user_context=user_context,
    )

    media_ids: list[int] = []
    for c in final_candidates[:batch_size]:
        media_ids.append(c.id)

    cached_whys_map: dict[int, CachedWhy] = {}
    if media_ids:
        cached_whys_map = await why_cache.get_many(
            user_id=user_id,
            media_type=req.media_type,
            media_ids=media_ids,
        )

    uncached_candidates = []
    uncached_media_ids: list[int] = []
    cached_whys_meta: dict[str, dict] = {}

    for c in final_candidates[:batch_size]:
        cached = cached_whys_map.get(c.id)
        if cached:
            cached_whys_meta[str(c.id)] = {
                "why_md": cached.why_md,
                "imdb_rating": cached.imdb_rating,
                "rotten_tomatoes_rating": cached.rt_rating,
            }
        else:
            uncached_candidates.append(c)
            uncached_media_ids.append(c.id)

    request_meta = {
        "recipe": "for_you_feed@v1",
        "items_brief": [
            {
                "media_id": (c.payload or {}).get("media_id"),
                "title": (c.payload or {}).get("title"),
            }
            for c in final_candidates[:batch_size]
        ],
    }

    llm_prompts: PromptsEnvelope | None = None
    if uncached_candidates:
        llm_prompts = recipe.build_prompt(
            query_text=None,
            batch_size=len(uncached_candidates),
            user_context=user_context,
            candidates=uncached_candidates,
        )

        ticket = Ticket(
            user_id=user_id,
            prompts=llm_prompts.model_dump(mode="json") if llm_prompts else {},
            meta=request_meta,
        )

        await store.put(
            req.query_id,  # ticket key
            ticket,
            ttl_sec=IDLE_TTL_SEC,
        )

    asyncio.create_task(
        logger.log_query_intake(
            endpoint=ENDPOINT,
            query_id=req.query_id,
            user_id=user_id,
            session_id=req.session_id,
            media_type=req.media_type,
            query_filters=req.query_filters,
            ctx_log=ctx_log,
            pipeline_version=PIPELINE_VERSION,
            batch_size=batch_size,
            device_info=req.device_info,
            request_meta=request_meta,
        )
    )

    asyncio.create_task(
        logger.log_candidates(
            endpoint=ENDPOINT,
            query_id=req.query_id,
            media_type=req.media_type,
            candidates=final_candidates[:batch_size],
            traces=traces,
            stage="final",
        )
    )

    items = []
    for c in final_candidates[:batch_size]:
        item = _for_you_item_view(c)
        if str(c.id) in cached_whys_meta:
            item.update(cached_whys_meta[str(c.id)])
            item["why_source"] = "cache"
        else:
            item["why_source"] = "llm"
        items.append(item)

    return JSONResponse(
        {
            "query_id": req.query_id,
            "items": items,
            "active_subs": user_context.active_subscriptions,
            "stream_url": f"/discovery/for-you/why?query_id={req.query_id}"
            if uncached_candidates
            else None,
        }
    )


@router.get("/for-you/why")
async def for_you_why_stream(
    query_id: str,
    batch: int = 1,
    user_id: str = Depends(get_current_user_id),
    store=Depends(get_ticket_store),
    chat_llm=Depends(get_chat_completion_llm),
):
    """Stream personalized 'why you'll like it' explanations for for-you results."""
    ticket = await store.get(query_id)
    if not ticket:
        raise HTTPException(404, "Unknown or expired query")
    if ticket.user_id != user_id:
        raise HTTPException(403, "Forbidden")
    await store.touch(query_id, IDLE_TTL_SEC)

    try:
        env = PromptsEnvelope.model_validate(ticket.prompts)
    except Exception as e:
        raise HTTPException(500, f"Invalid prompt envelope: {e}")

    picked = pick_call(env, batch)
    messages = picked["messages"]
    batch_id = picked["batch_id"]

    model = env.model
    params = dict(env.params or {})

    def gen() -> Iterator[bytes]:
        last_hb = time.time()
        yield sse(
            "started",
            {
                "query_id": query_id,
                "batch_id": batch_id,
            },
        )

        # Global JSONL: buffer by newline and emit per-item deltas
        buffer = ""
        try:
            stream_iter = chat_llm.stream(messages, model=model, **params)
            for delta in stream_iter:
                # Heartbeat
                now = time.time()
                if now - last_hb >= HEARTBEAT_SEC:
                    yield b":\n\n"  # comment frame
                    last_hb = now

                buffer += delta
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        media_id = obj.get("media_id")
                        imdb_rating = obj.get("imdb_rating")
                        rotten_tomatoes_rating = obj.get("rotten_tomatoes_rating")
                        why_md = obj.get("why_md")
                        if not media_id or not isinstance(why_md, str):
                            continue
                        yield sse(
                            "why_delta",
                            {
                                "media_id": media_id,
                                "imdb_rating": imdb_rating,
                                "rotten_tomatoes_rating": rotten_tomatoes_rating,
                                "why_you_might_enjoy_it": why_md,
                            },
                        )
                    except json.JSONDecodeError:
                        # Incomplete JSON line; keep buffering
                        buffer = line + "\n" + buffer
                        break
            # Flush a trailing JSON line if complete
            tail = buffer.strip()
            if tail:
                try:
                    obj = json.loads(tail)
                    media_id = obj.get("media_id")
                    imdb_rating = obj.get("imdb_rating")
                    rotten_tomatoes_rating = obj.get("rotten_tomatoes_rating")
                    why_md = obj.get("why_md")
                    if media_id and isinstance(why_md, str):
                        yield sse(
                            "why_delta",
                            {
                                "media_id": media_id,
                                "imdb_rating": imdb_rating,
                                "rotten_tomatoes_rating": rotten_tomatoes_rating,
                                "why_you_might_enjoy_it": why_md,
                            },
                        )
                except Exception:
                    pass

            yield sse("done", {"ok": True})
        except Exception:
            error_id = str(uuid.uuid4())
            log.exception("For-you why stream failed (error_id=%s)", error_id)
            yield sse(
                "error",
                {
                    "message": "Something went wrong. Please try again.",
                    "error_id": error_id,
                },
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
        },
    )


def _for_you_item_view(c) -> dict:
    """Convert a candidate to item view for for-you feed (without imdb_rating/rt_score)."""
    p = c.payload or {}
    return {
        "id": c.id,
        "media_id": p.get("media_id"),
        "title": p.get("title"),
        "release_year": p.get("release_year"),
        "genres": p.get("genres", []),
        "poster_url": p.get("poster_url"),
        "backdrop_url": p.get("backdrop_url"),
        "trailer_key": p.get("trailer_key"),
    }