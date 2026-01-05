import asyncio
from collections.abc import AsyncIterator
import json
from pydantic import BaseModel, ValidationError

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from reelix_agent.core.types import PromptsEnvelope, RecQuerySpec
from reelix_agent.orchestrator.orchestrator_agent_v1 import (
    InteractiveAgentInput,
    # run_orchestrator_agent,
    run_rec_engine_direct,
    plan_orchestrator_agent,
    execute_orchestrator_plan,
)
from reelix_agent.orchestrator.active_spec import craft_active_spec
from reelix_agent.explanation.explanation_prompts import build_why_prompt_envelope
from reelix_agent.explanation.explanation_agent import stream_why_events

from app.deps.deps import (
    get_agent_rec_runner,
    get_logger,
)
from app.deps.deps_llm import get_chat_completion_llm
from app.deps.deps_redis_caches import get_ticket_store, get_state_store
from app.deps.supabase_client import (
    get_current_user_id,
    get_user_context_service,
)
from app.agent.session_memory_service import upsert_session_memory
from app.infrastructure.cache.ticket_store import Ticket
from app.schemas import InteractiveRequest, ExploreRerunRequest

router = APIRouter(prefix="/discovery", tags=["explore"])

ENDPOINT = "discovery/explore"
IDLE_TTL_SEC = 15 * 60
HEARTBEAT_SEC = 15


@router.post("/explore")
async def agent_interactive_stream(
    req: InteractiveRequest,
    batch_size: int = 20,
    user_id: str = Depends(get_current_user_id),
    agent_rec_runner=Depends(get_agent_rec_runner),
    user_context_svc=Depends(get_user_context_service),
    chat_llm=Depends(get_chat_completion_llm),
    logger=Depends(get_logger),
    ticket_store=Depends(get_ticket_store),
    state_store=Depends(get_state_store),
):
    """
    Streaming /discover/explore endpoint.

    Emits SSE events so the UI can render an opening summary + active_spec immediately, while the curator runs in the background.

    Events:
      - started: {query_id}
      - opening: {query_id, opening_summary, active_spec}
      - recs: {query_id, items, stream_url}
      - done / error
    """
    session_state = await state_store.get_session(session_id=req.session_id, touch=True)

    agent_input = InteractiveAgentInput(
        user_id=user_id,
        query_id=req.query_id,
        session_id=req.session_id,
        media_type=req.media_type,
        query_text=req.query_text,
        session_memory=session_state.to_orchestrator() if session_state else None,
        user_context_service=user_context_svc,
        batch_size=batch_size,
        device_info=req.device_info,
    )

    async def gen() -> AsyncIterator[bytes]:
        yield _sse("started", {"query_id": req.query_id})

        try:
            # 1) Orchestrator "plan" step (fast) — get tool args (spec + opening_summary)
            state, plan = await plan_orchestrator_agent(
                agent_input=agent_input, llm_client=chat_llm
            )

            # fast UI paint with opening summary + active_spec for chip display in RECS mode
            if plan.mode == "recs":
                yield _sse(
                    "opening",
                    {
                        "query_id": req.query_id,
                        "opening_summary": plan.opening_summary,
                        "active_spec": craft_active_spec(state.query_spec).model_dump(
                            mode="json"
                        )
                        if state.query_spec
                        else None,
                    },
                )

            # 2) Execute the recommendation agent, but keep SSE connection alive with heartbeats.
            task = asyncio.create_task(
                execute_orchestrator_plan(
                    state=state,
                    plan=plan,
                    agent_rec_runner=agent_rec_runner,
                    user_context_service=user_context_svc,
                    llm_client=chat_llm,
                )
            )

            try:
                while True:
                    done, _pending = await asyncio.wait({task}, timeout=HEARTBEAT_SEC)
                    if task in done:
                        agent_result = task.result()
                        break

                    # SSE heartbeat comment frame (doesn't trigger client handlers)
                    yield b":\n\n"

            except asyncio.CancelledError:
                # client disconnected -> stop the background work too
                task.cancel()
                raise

            # 3) Persist session memory
            asyncio.create_task(
                upsert_session_memory(
                    state_store=state_store,
                    session_id=req.session_id,
                    user_id=user_id,
                    agent_result=agent_result,
                )
            )

            # 4) Query/recs logging
            mode = agent_result.mode
            ctx_log = agent_result.ctx_log
            traces = agent_result.pipeline_traces[-1] if agent_result.pipeline_traces else {}
            meta = agent_result.meta

            asyncio.create_task(
                logger.log_query_intake(
                    endpoint=ENDPOINT,
                    query_id=req.query_id,
                    user_id=user_id,
                    session_id=req.session_id,
                    media_type=req.media_type,
                    query_text=req.query_text,
                    ctx_log=ctx_log,
                    pipeline_version="RecommendPipeline@v4",
                    batch_size=batch_size,
                    device_info=req.device_info,
                    request_meta=meta,
                )
            )

            # also log final recs for RECS mode
            if str(mode) == "recs":
                asyncio.create_task(
                    logger.log_candidates(
                        endpoint=ENDPOINT,
                        query_id=req.query_id,
                        media_type=req.media_type,
                        candidates=agent_result.candidates,
                        traces=traces,
                        stage="prompt_context",
                    )
                )

            # 5) Branch response for CHAT / RECS mode

            # == CHAT mode: stream chat message & done ==
            if str(mode) == "chat":
                yield _sse("chat", {"query_id": req.query_id, "message": plan.message})
                yield _sse("done", {"ok": True})
                return

            # == RECS mode: write ticket store and stream final recs ==
            final_recs = agent_result.final_recs
            query_spec = agent_result.query_spec

            if final_recs and query_spec:
                why_agent_prompts = build_why_prompt_envelope(
                    candidates=final_recs,
                    query_spec=query_spec,
                    batch_size=8,
                )
                ticket = Ticket(
                    user_id=user_id,
                    prompts=why_agent_prompts.model_dump(mode="json")
                    if why_agent_prompts
                    else {},
                )
                await ticket_store.put(req.query_id, ticket, ttl_sec=IDLE_TTL_SEC)

            items = [_item_view(c) for c in (agent_result.final_recs or [])]

            yield _sse(
                "recs",
                {
                    "query_id": req.query_id,
                    "curator_opening": agent_result.summary,
                    "items": items,
                    "stream_url": f"/discovery/explore/why?query_id={req.query_id}",
                },
            )
            yield _sse("done", {"ok": True})

        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
        },
    )


@router.post("/explore/rerun")
async def agent_explore_rerun(
    req: ExploreRerunRequest,
    batch_size: int = 20,
    user_id: str = Depends(get_current_user_id),
    agent_rec_runner=Depends(get_agent_rec_runner),
    user_context_svc=Depends(get_user_context_service),
    chat_llm=Depends(get_chat_completion_llm),
    logger=Depends(get_logger),
    ticket_store=Depends(get_ticket_store),
    state_store=Depends(get_state_store),
):
    """
    Chip rerun endpoint: patch provider/year filters and rerun the SAME pipeline path
    as the orchestrator tool call, without calling the orchestrator LLM.
    """
    session_state = await state_store.get_session(session_id=req.session_id, touch=True)
    if not session_state:
        raise HTTPException(404, "Unknown or expired session")
    if session_state.user_id != user_id:
        raise HTTPException(403, "Forbidden")
    if not session_state.last_spec:
        raise HTTPException(409, "Last_spec does not exist. Call /explore instead.")

    # 1) Load last_spec from session state -> RecQuerySpec
    try:
        base_spec = RecQuerySpec.model_validate(session_state.last_spec)
    except ValidationError as e:
        raise HTTPException(500, f"Invalid last_spec in session state: {e}")

    # 2) Apply deterministic patch (ONLY filters)
    spec = base_spec.model_copy(deep=True)

    if _field_provided(req.patch, "providers"):
        spec.providers = list(
            req.patch.providers or []
        )  # null => clear, list => replace

    if _field_provided(req.patch, "year_range"):
        if req.patch.year_range is None:
            spec.year_range = None
        else:
            if len(req.patch.year_range) != 2:
                raise HTTPException(
                    400, "year_range must be [start_year, end_year] or null"
                )
            spec.year_range = (
                int(req.patch.year_range[0]),
                int(req.patch.year_range[1]),
            )

    # 3) Build an AgentState (for seen_ids + consistent bookkeeping) BUT do not call LLM
    agent_input = InteractiveAgentInput(
        user_id=user_id,
        query_id=req.query_id,
        session_id=req.session_id,
        media_type=spec.media_type,
        query_text=spec.query_text,
        session_memory=session_state.to_orchestrator(),
        user_context_service=user_context_svc,
        batch_size=batch_size,
        device_info=req.device_info,
    )

    # 5) Convert state -> InteractiveAgentResult
    agent_result = await run_rec_engine_direct(
        agent_input=agent_input,
        spec=spec,
        agent_rec_runner=agent_rec_runner,
        user_context_service=user_context_svc,
        llm_client=chat_llm,
    )

    # 6) Upsert session memory using existing code
    await upsert_session_memory(
        state_store=state_store,
        session_id=req.session_id,
        user_id=user_id,
        agent_result=agent_result,
    )

    # 7) Logging (same as /explore)
    ctx_log = agent_result.ctx_log
    traces = agent_result.pipeline_traces[-1] if agent_result.pipeline_traces else {}
    meta = agent_result.meta

    asyncio.create_task(
        logger.log_query_intake(
            endpoint=ENDPOINT,
            query_id=req.query_id,
            user_id=user_id,
            session_id=req.session_id,
            media_type=str(spec.media_type),
            query_text=spec.query_text,
            ctx_log=ctx_log,
            pipeline_version="RecommendPipeline@v4",
            batch_size=batch_size,
            device_info=req.device_info,
            request_meta=meta,
        )
    )

    asyncio.create_task(
        logger.log_candidates(
            endpoint=ENDPOINT,
            query_id=req.query_id,
            media_type=str(spec.media_type),
            candidates=agent_result.candidates,
            traces=traces,
            stage="chip_rerun",
        )
    )

    # 8) WHY ticket (same as /explore)
    final_recs = agent_result.final_recs
    query_spec = agent_result.query_spec

    if final_recs and query_spec:
        why_agent_prompts = build_why_prompt_envelope(
            candidates=final_recs,
            query_spec=query_spec,
            batch_size=8,
        )
        ticket = Ticket(
            user_id=user_id,
            prompts=why_agent_prompts.model_dump(mode="json")
            if why_agent_prompts
            else {},
        )
        await ticket_store.put(req.query_id, ticket, ttl_sec=IDLE_TTL_SEC)

    active_spec = craft_active_spec(query_spec) if query_spec else None
    items = [_item_view(c) for c in final_recs]

    return JSONResponse(
        {
            "query_id": req.query_id,
            "mode": "RECS",
            "active_spec": active_spec.model_dump(mode="json") if active_spec else None,
            "items": items,
            "stream_url": f"/discovery/explore/why?query_id={req.query_id}",
        }
    )


@router.get("/explore/why")
async def stream_why(
    query_id: str,
    batch: int = 1,
    user_id: str = Depends(get_current_user_id),
    store=Depends(get_ticket_store),
    chat_llm=Depends(get_chat_completion_llm),  # must expose async chat_stream(...)
):
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

    picked = _pick_call(env, batch)
    messages = picked["messages"]
    batch_id = picked["batch_id"]

    model = env.model
    params = dict(env.params or {})

    async def gen() -> AsyncIterator[bytes]:
        yield _sse("started", {"query_id": query_id, "batch_id": batch_id})

        try:
            async for ev in stream_why_events(
                chat_llm=chat_llm,
                messages=messages,
                model=model,
                params=params,
                heartbeat_sec=HEARTBEAT_SEC,
            ):
                if ev.type == "heartbeat":
                    # SSE heartbeat comment frame
                    yield b":\n\n"
                    continue

                item = ev.item
                if item is None:
                    continue

                yield _sse(
                    "why_delta",
                    {
                        "media_id": item.media_id,
                        "why_you_might_enjoy_it": item.why,
                    },
                )

            yield _sse("done", {"ok": True})

        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
        },
    )


def _item_view(c):
    p = c.payload or {}
    return {
        "id": c.id,
        "media_id": p.get("media_id"),
        "title": p.get("title"),
        "release_year": p.get("release_year"),
        "genres": p.get("genres", []),
        "imdb_rating": p.get("imdb_rating", 0.0),
        "rt_score": p.get("rt_score", "N/A"),
        "poster_url": p.get("poster_url"),
        "backdrop_url": p.get("backdrop_url"),
        "trailer_key": p.get("trailer_key"),
    }


def _field_provided(model: BaseModel, name: str) -> bool:
    # pydantic v2: model_fields_set, v1: __fields_set__
    s = getattr(model, "model_fields_set", None)
    if s is None:
        s = getattr(model, "__fields_set__", set())
    return name in (s or set())


def _pick_call(env: PromptsEnvelope, batch: int | None) -> dict:
    if not env.calls:
        raise HTTPException(500, "Envelope has no calls")

    call = None
    if batch is not None:
        for c in env.calls:
            if getattr(c, "call_id", None) == batch:
                call = c
                break
        if call is None:
            raise HTTPException(404, f"Batch {batch} not found")
    else:
        call = env.calls[0]

    return {
        "messages": call.messages,
        "items_brief": getattr(call, "items_brief", []),
        "media_id": getattr(call, "media_id", None),
        "batch_id": getattr(call, "call_id", None),
    }


def _sse(event: str, data: dict | str) -> bytes:
    if isinstance(data, dict):
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = data
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
