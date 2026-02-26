"""
/discovery/explore endpoints. Agent-powered vibe search with streaming SSE responses.
"""

import asyncio
from collections.abc import AsyncIterator
import logging
import time
import uuid
from pydantic import BaseModel, ValidationError

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from reelix_agent.core.types import PromptsEnvelope, RecQuerySpec, ExploreAgentInput
from reelix_agent.orchestrator.orchestrator_agent import (
    run_rec_engine_direct,
    plan_orchestrator_agent,
    execute_orchestrator_plan,
)
from reelix_agent.orchestrator.active_spec import craft_active_spec
from reelix_agent.explanation.explanation_prompts import build_why_prompt_envelope
from reelix_agent.explanation.explanation_agent import stream_why_events
from reelix_agent.reflection import generate_next_steps
from reelix_agent.reflection.reflection_agent import REFLECTION_MODEL
from reelix_logging.rec_logger import ReflectionLog

from app.deps.deps import (
    get_agent_rec_runner,
    get_logger,
)
from app.deps.deps_llm import get_chat_completion_llm
from app.deps.deps_redis_caches import get_ticket_store, get_state_store
from app.deps.deps_tools import get_tool_registry, get_tool_runner
from app.deps.supabase_client import (
    get_current_user_id,
    get_user_context_service,
)
from app.services.session_memory import upsert_session_memory
from app.infrastructure.cache.ticket_store import Ticket
from app.schemas import InteractiveRequest, ExploreRerunRequest

from ._helpers import sse, item_view, pick_call

router = APIRouter(tags=["explore"])

ENDPOINT = "discovery/explore"
IDLE_TTL_SEC = 15 * 60
HEARTBEAT_SEC = 15
log = logging.getLogger(__name__)


@router.post("/explore")
async def explore_stream(
    req: InteractiveRequest,
    batch_size: int = 20,
    user_id: str = Depends(get_current_user_id),
    agent_rec_runner=Depends(get_agent_rec_runner),
    user_context_svc=Depends(get_user_context_service),
    chat_llm=Depends(get_chat_completion_llm),
    logger=Depends(get_logger),
    ticket_store=Depends(get_ticket_store),
    state_store=Depends(get_state_store),
    tool_registry=Depends(get_tool_registry),
    tool_runner=Depends(get_tool_runner),
):
    """
    Streaming /discovery/explore endpoint.

    Emits SSE events so the UI can render an opening summary + active_spec immediately, followed by final recs, as well as stream_url for WHY explanations.

    Events:
      - started: {query_id}
      - opening: {query_id, opening_summary, active_spec}
      - recs: {query_id, items, stream_url}
      - done / error
    """
    session_state = await state_store.get_session(session_id=req.session_id, touch=True)
    print (session_state)

    agent_input = ExploreAgentInput(
        user_id=user_id,
        query_id=req.query_id,
        session_id=req.session_id,
        media_type=req.media_type,
        query_text=req.query_text,
        session_memory=session_state.to_orchestrator() if session_state else None,
        batch_size=batch_size,
        device_info=req.device_info,
    )

    async def gen() -> AsyncIterator[bytes]:
        yield sse("started", {"query_id": req.query_id})

        try:
            # 1) Orchestrator "plan" step (fast) — get tool args (spec + opening_summary)
            state, plan = await plan_orchestrator_agent(
                agent_input=agent_input,
                llm_client=chat_llm,
                tool_registry=tool_registry,
                logger=logger,
            )

            # fast UI paint with opening summary + active_spec for chip display (RECS mode only)
            if plan.mode == "recs":
                yield sse(
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

            # 2) Execute the recommendation agent, keeping SSE connection alive with heartbeats.
            task = asyncio.create_task(
                execute_orchestrator_plan(
                    state=state,
                    plan=plan,
                    agent_rec_runner=agent_rec_runner,
                    llm_client=chat_llm,
                    tool_registry=tool_registry,
                    tool_runner=tool_runner,
                    logger=logger,
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

            # log query intake
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

            # log final recs (RECS mode only)
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
                yield sse("chat", {"query_id": req.query_id, "message": plan.message})
                yield sse("done", {"ok": True})
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

            items = [item_view(c) for c in (agent_result.final_recs or [])]

            yield sse(
                "recs",
                {
                    "query_id": req.query_id,
                    "curator_opening": agent_result.summary,
                    "items": items,
                    "stream_url": f"/discovery/explore/why?query_id={req.query_id}",
                },
            )

            # Clear stale last_admin_message before reflection attempt
            def _clear_admin_msg(payload: dict) -> None:
                summary = payload.get("summary")
                if isinstance(summary, dict):
                    summary.pop("last_admin_message", None)
                    # Keep last_reflection_strategy — need it for the next reflection call

            await state_store.update_session(
                session_id=req.session_id,
                ttl_sec=IDLE_TTL_SEC,
                mutate=_clear_admin_msg,
            )

            # Reflection agent: suggest next steps (best-effort, skip on timeout/error)
            if final_recs and query_spec:
                # Read previous strategy from session to avoid repeating
                _prev_strategy = None
                if session_state and session_state.summary:
                    _prev_strategy = session_state.summary.get("last_reflection_strategy")

                _refl_t0 = time.perf_counter()
                _refl_status = "error"
                reflection = None
                try:
                    reflection = await asyncio.wait_for(
                        generate_next_steps(
                            chat_llm=chat_llm,
                            query_spec=query_spec,
                            final_recs=final_recs,
                            tier_stats=agent_result.tier_stats,
                            previous_strategy=_prev_strategy,
                        ),
                        timeout=10.0,
                    )
                    _refl_status = "success" if reflection else "error"
                except asyncio.TimeoutError:
                    _refl_status = "timeout"
                    log.warning("Reflection agent timed out")
                except Exception:
                    _refl_status = "error"
                    log.warning("Reflection agent failed")

                _refl_ms = int((time.perf_counter() - _refl_t0) * 1000)

                # Log reflection attempt (fire-and-forget)
                asyncio.create_task(
                    logger.log_reflection(ReflectionLog(
                        query_id=req.query_id,
                        session_id=req.session_id,
                        user_id=user_id,
                        strategy=reflection.strategy if reflection else None,
                        suggestion=reflection.suggestion if reflection else None,
                        status=_refl_status,
                        latency_ms=_refl_ms,
                        input_tokens=reflection.input_tokens if reflection else None,
                        output_tokens=reflection.output_tokens if reflection else None,
                        model=REFLECTION_MODEL,
                        tier_stats=agent_result.tier_stats,
                    ))
                )

                if reflection:
                    yield sse(
                        "next_steps",
                        {
                            "query_id": req.query_id,
                            "strategy": reflection.strategy,
                            "text": reflection.suggestion,
                        },
                    )
                    # Persist as last_admin_message + last_reflection_strategy for next-turn context
                    next_steps_text = reflection.suggestion
                    next_steps_strategy = reflection.strategy
                    def _patch(payload: dict) -> None:
                        summary = payload.setdefault("summary", {})
                        if isinstance(summary, dict):
                            summary["last_admin_message"] = next_steps_text
                            summary["last_reflection_strategy"] = next_steps_strategy

                    asyncio.create_task(
                        state_store.update_session(
                            session_id=req.session_id,
                            ttl_sec=IDLE_TTL_SEC,
                            mutate=_patch,
                        )
                    )

            yield sse("done", {"ok": True})

        except Exception:
            error_id = str(uuid.uuid4())
            log.exception("Explore stream failed (error_id=%s)", error_id)
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


@router.post("/explore/rerun")
async def explore_rerun(
    req: ExploreRerunRequest,
    batch_size: int = 20,
    user_id: str = Depends(get_current_user_id),
    agent_rec_runner=Depends(get_agent_rec_runner),
    user_context_svc=Depends(get_user_context_service),
    chat_llm=Depends(get_chat_completion_llm),
    logger=Depends(get_logger),
    ticket_store=Depends(get_ticket_store),
    state_store=Depends(get_state_store),
    tool_registry=Depends(get_tool_registry),
    tool_runner=Depends(get_tool_runner),
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
    agent_input = ExploreAgentInput(
        user_id=user_id,
        query_id=req.query_id,
        session_id=req.session_id,
        media_type=spec.media_type,
        query_text=spec.query_text,
        session_memory=session_state.to_orchestrator(),
        batch_size=batch_size,
        device_info=req.device_info,
    )

    # 4) Convert state -> InteractiveAgentResult
    agent_result = await run_rec_engine_direct(
        agent_input=agent_input,
        spec=spec,
        agent_rec_runner=agent_rec_runner,
        llm_client=chat_llm,
        tool_registry=tool_registry,
        tool_runner=tool_runner,
        logger=logger,
    )

    # 5) Upsert session memory
    await upsert_session_memory(
        state_store=state_store,
        session_id=req.session_id,
        user_id=user_id,
        agent_result=agent_result,
    )

    # 6) Logging (same as /explore)
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

    # 7) WHY ticket (same as /explore)
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
    items = [item_view(c) for c in final_recs]

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
async def explore_why_stream(
    query_id: str,
    batch: int = 1,
    user_id: str = Depends(get_current_user_id),
    store=Depends(get_ticket_store),
    chat_llm=Depends(get_chat_completion_llm),
):
    """Stream personalized 'why you'll like it' explanations for explore results."""
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

    async def gen() -> AsyncIterator[bytes]:
        yield sse("started", {"query_id": query_id, "batch_id": batch_id})

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

                yield sse(
                    "why_delta",
                    {
                        "media_id": item.media_id,
                        "why_you_might_enjoy_it": item.why,
                    },
                )

            yield sse("done", {"ok": True})

        except Exception:
            error_id = str(uuid.uuid4())
            log.exception("Explore why stream failed (error_id=%s)", error_id)
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


def _field_provided(model: BaseModel, name: str) -> bool:
    """Check if a field was explicitly provided in the request."""
    # pydantic v2: model_fields_set, v1: __fields_set__
    s = getattr(model, "model_fields_set", None)
    if s is None:
        s = getattr(model, "__fields_set__", set())
    return name in (s or set())