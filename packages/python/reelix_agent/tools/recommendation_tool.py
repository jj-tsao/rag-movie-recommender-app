"""
Recommendation agent tool implementation.

Runs the full recommendation pipeline: retrieval → ranking → curator LLM evaluation → tier selection.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

from anyio import to_thread

from reelix_agent.core.types import AgentMode, RecQuerySpec
from reelix_agent.curator.curator_agent import run_curator_agent
from reelix_agent.curator.curator_tiers import apply_curator_tiers
from reelix_agent.tools.types import ToolCategory, ToolContext, ToolResult, ToolSpec

if TYPE_CHECKING:
    from reelix_logging.rec_logger import TelemetryLogger

# JSON Schema for the recommendation_agent tool parameters
RECOMMENDATION_AGENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rec_query_spec": {
            "type": "object",
            "description": (
                "Structured rec_query_spec describing the recommendation query: "
                "intent, media type, core genres, sub-genres, tone, and structural/thematic preferences."
            ),
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": (
                        "Compact retrieval-oriented description of what the user wants. "
                        "Include genre/vibe/tone/structure. Exclude greetings and meta-instructions."
                    ),
                },
                "media_type": {
                    "type": "string",
                    "description": "Type of media to recommend. Use 'movie'",
                    "enum": ["movie"],
                },
                "core_genres": {
                    "type": "array",
                    "description": (
                        "List of canonical genre names to prioritize/include "
                        "(e.g., 'Drama', 'Comedy', 'Science Fiction')."
                    ),
                    "items": {
                        "type": "string",
                        "enum": [
                            "Action",
                            "Comedy",
                            "Drama",
                            "Romance",
                            "Science Fiction",
                            "Thriller",
                            "Adventure",
                            "Animation",
                            "Crime",
                            "Documentary",
                            "Family",
                            "Fantasy",
                            "History",
                            "Horror",
                            "Music",
                            "Mystery",
                            "War",
                            "Western",
                        ],
                    },
                },
                "sub_genres": {
                    "type": "array",
                    "description": (
                        "List of more specific sub-genre descriptors such as "
                        "'psychological thriller', 'romantic comedy', 'neo-noir', 'dark fantasy'."
                    ),
                    "items": {"type": "string"},
                },
                "core_tone": {
                    "type": "array",
                    "description": (
                        "List of tone/vibe adjectives for how the content should feel emotionally, "
                        "such as 'satirical', 'cozy', 'bleak', 'uplifting'."
                    ),
                    "items": {"type": "string"},
                },
                # "narrative_shape": {
                #     "type": "array",
                #     "description": (
                #         "List of requested narrative or structural properties, such as "
                #         "'plot twists', 'slow-burn', 'nonlinear', 'fast-paced'."
                #     ),
                #     "items": {"type": "string"},
                # },
                "key_themes": {
                    "type": "array",
                    "description": (
                        "List of thematic ideas or subject-matter concerns, such as "
                        "'existential', 'class satire', 'coming-of-age', 'identity'."
                    ),
                    "items": {"type": "string"},
                },
                "providers": {
                    "type": "array",
                    "description": "Optional list of streaming providers to include.",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Netflix",
                            "Hulu",
                            "HBO Max",
                            "Disney+",
                            "Apple TV+",
                            "Amazon Prime Video",
                            "Paramount+",
                            "Peacock Premium",
                            "MGM+",
                            "Starz",
                            "AMC+",
                            "Crunchyroll",
                            "BritBox",
                            "Acorn TV",
                            "Criterion Channel",
                            "Tubi TV",
                            "Pluto TV",
                            "The Roku Channel",
                        ],
                    },
                },
                "year_range": {
                    "description": (
                        "Optional release-year range as [start_year, end_year] (inclusive). "
                        "If the user does not specify a year range, set to null."
                    ),
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 1970, "maximum": 2100},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        {"type": "null"},
                    ],
                    "default": None,
                },
                "mentioned_titles": {
                    "type": "array",
                    "description": (
                        "Movie titles explicitly mentioned by user as examples "
                        "(e.g., 'I like Interstellar', 'similar to The Matrix'). "
                        "Extract title only. These will be automatically excluded from results."
                    ),
                    "items": {"type": "string"},
                    "default": [],
                },
            },
            "required": ["query_text"],
            "additionalProperties": False,
        },
        "memory_delta": {
            "type": "object",
            "description": "Minimal session memory delta for this turn.",
            "properties": {
                "turn_kind": {
                    "type": "string",
                    "enum": ["new", "refine", "chat"],
                },
                "recent_feedback": {
                    "type": ["object", "null"],
                    "description": (
                        "Only include when user is reacting to prior recommendations "
                        "or iterating on the last slate. Otherwise null."
                    ),
                    "properties": {
                        "liked_slots": {"type": "array", "items": {"type": "string"}},
                        "disliked_slots": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": "string"},
                    },
                    "required": ["liked_slots", "disliked_slots", "notes"],
                    "additionalProperties": False,
                },
            },
            "required": ["turn_kind", "recent_feedback"],
            "additionalProperties": False,
        },
        "opening_summary": {
            "type": "string",
            "description": (
                "Exactly 2 sentences (max ~220 chars). "
                "Summarize the user's current request based on rec_query_spec. "
                "Do NOT name specific titles. Do NOT promise outcomes."
            ),
        },
    },
    "required": ["rec_query_spec", "memory_delta", "opening_summary"],
    "additionalProperties": False,
}


async def handle_recommendation_agent(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    """Execute the recommendation agent tool.

    The main rec tool that:
    1. Parses RecQuerySpec from args
    2. Runs the recommendation pipeline
    3. Runs curator LLM agent for final evaluation
    4. Applies curator tiers for final selection
    5. Updates AgentState with results

    Args:
        ctx: ToolContext with state, agent_rec_runner, llm_client
        args: Tool arguments containing rec_query_spec, memory_delta, opening_summary

    Returns:
        ToolResult with count and tier_stats in payload
    """
    state = ctx.state

    # 1) Parse arguments
    turn_mem = args.get("memory_delta")
    if isinstance(turn_mem, dict):
        state.turn_memory = turn_mem
        state.turn_kind = turn_mem.get("turn_kind") # for rec engine to apply seen_id penalty when refining

    raw_spec = args.get("rec_query_spec") or {}
    try:
        spec = RecQuerySpec(**raw_spec)
    except Exception as e:
        return ToolResult.error(f"Invalid rec_query_spec: {e}")

    # Extract mentioned_titles and store in spec for filtering
    mentioned_titles = raw_spec.get("mentioned_titles") or []
    if mentioned_titles:
        spec.seed_titles = mentioned_titles
        print(f"[recommendation_tool] Will exclude mentioned titles: {mentioned_titles}")

    state.query_spec = spec
    state.turn_mode = AgentMode.RECS

    # 2) Run recommendation pipeline
    def _run_pipeline_sync():
        return ctx.agent_rec_runner.run_for_agent(
            user_context=state.user_context,
            spec=spec,
            seen_media_ids=state.seen_media_ids,
            turn_kind=state.turn_kind,
        )

    pipeline_start = time.perf_counter()
    candidates, traces, ctx_log = await to_thread.run_sync(_run_pipeline_sync)
    pipeline_ms = (time.perf_counter() - pipeline_start) * 1000
    print(f"[timing] rec_pipeline_sync_ms={pipeline_ms:.1f}")

    state.candidates = candidates
    if traces:
        state.pipeline_traces.append(traces)
    if ctx_log:
        state.ctx_log = ctx_log

    # 3) Run curator agent with parallel batching
    curator_start = time.perf_counter()

    # Split candidates into 2 batches of ~6 each for parallel evaluation
    mid_point = len(candidates) // 2
    batch_1 = candidates[:mid_point]
    batch_2 = candidates[mid_point:]

    print(f"[curator] Running parallel batches: {len(batch_1)} + {len(batch_2)} candidates")

    # Run both batches in parallel
    batch_1_output, batch_2_output = await asyncio.gather(
        run_curator_agent(
            query_text=spec.query_text,
            spec=state.query_spec,
            candidates=batch_1,
            llm_client=ctx.llm_client,
            user_signals=None,
        ),
        run_curator_agent(
            query_text=spec.query_text,
            spec=state.query_spec,
            candidates=batch_2,
            llm_client=ctx.llm_client,
            user_signals=None,
        ),
    )

    # Merge results
    curator_output = _merge_curator_outputs(batch_1_output, batch_2_output)

    curator_ms = (time.perf_counter() - curator_start) * 1000
    print(f"[timing] curator_llm_ms={curator_ms:.1f} (parallel batches)")

    # 4) Parse curator output
    parse_start = time.perf_counter()
    try:
        curator_data = json.loads(curator_output)
    except json.JSONDecodeError as e:
        return ToolResult.error(f"Curator output parse error: {e}")
    parse_ms = (time.perf_counter() - parse_start) * 1000
    print(f"[timing] curator_parse_ms={parse_ms:.1f}")

    state.curator_eval = curator_data.get("evaluation_results", [])

    # 5) Apply curator tiers for final selection
    tiers_start = time.perf_counter()
    state.final_recs, tier_stats = apply_curator_tiers(
        evaluation_results=state.curator_eval,
        candidates=state.candidates,
        limit=spec.num_recs or 8,
    )
    tiers_ms = (time.perf_counter() - tiers_start) * 1000
    print(f"[timing] curator_tiers_ms={tiers_ms:.1f}")

    # Store tier_stats in state for downstream logging
    state.tier_stats = {
        **tier_stats,
        "curator_latency_ms": int(curator_ms),
        "tier_latency_ms": int(tiers_ms),
    }

    # 5b) Log curator evaluations and tier summary (async, fire-and-forget)
    logger: TelemetryLogger | None = ctx.extra.get("logger")
    if logger:
        asyncio.create_task(
            _log_curator_data(
                logger=logger,
                query_id=state.query_id,
                media_type=state.media_type,
                candidates=state.candidates,
                final_recs=state.final_recs,
                tier_stats=state.tier_stats,
            )
        )

    # 6) Record trace for multi-turn (appended to messages by orchestrator if needed)
    state.agent_trace.append(
        {
            "step": state.step_count,
            "tool": "recommendation_agent",
            "args": args,
            "result": {"count": len(state.final_recs)},
        }
    )

    # 7) Build result payload
    return ToolResult.success(
        payload={
            "count": len(state.final_recs),
            "tier_stats": tier_stats,
        },
        pipeline_ms=pipeline_ms,
        curator_ms=curator_ms,
        tiers_ms=tiers_ms,
    )


# Create the ToolSpec instance for registration
# NOTE: This must be after the handler function is defined
recommendation_agent_spec = ToolSpec(
    name="recommendation_agent",
    description=(
        "Run the Reelix recommendation pipeline for the current user using a rec_query_spec. "
        "Use this to retrieve, rank, and curate recommendations based on the user's request."
    ),
    inputSchema=RECOMMENDATION_AGENT_SCHEMA,
    category=ToolCategory.TERMINAL,
    handler=handle_recommendation_agent,
)


def _merge_curator_outputs(output1: str, output2: str) -> str:
    """Merge two curator JSON outputs into a single output.

    Args:
        output1: JSON string from first batch
        output2: JSON string from second batch

    Returns:
        Merged JSON string with combined evaluation_results
    """
    try:
        data1 = json.loads(output1)
        data2 = json.loads(output2)

        merged = {
            "evaluation_results": data1.get("evaluation_results", []) + data2.get("evaluation_results", [])
        }

        return json.dumps(merged)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to merge curator outputs: {e}")


async def _log_curator_data(
    *,
    logger: "TelemetryLogger",
    query_id: str,
    media_type: str,
    candidates: list,
    final_recs: list,
    tier_stats: dict,
) -> None:
    """Log curator evaluations and tier summary to Supabase.

    Args:
        logger: TelemetryLogger instance
        query_id: Query identifier
        media_type: Media type (movie/tv)
        candidates: All candidates with curator scores stamped on payload
        final_recs: Final selected recommendations
        tier_stats: Tier statistics from apply_curator_tiers
    """
    # Lazy import to avoid circular dependency
    from reelix_logging.rec_logger import CuratorEvalLog, TierSummaryLog

    if not candidates:
        return

    # Build set of served media_ids for quick lookup
    served_ids = {int(c.id) for c in final_recs}

    # Build curator evaluation logs from final_recs first (with ranks)
    # Note: Pipeline scores (dense_score, sparse_score, pipeline_score) are stored
    # in rec_results table, not here. Join on query_id + media_id for analysis.
    evals = []
    for rank, c in enumerate(final_recs, start=1):
        p = c.payload or {}
        evals.append(
            CuratorEvalLog(
                query_id=query_id,
                media_id=int(c.id),
                media_type=media_type,
                title=p.get("title"),
                genre_fit=p.get("curator_genre_fit"),
                tone_fit=p.get("curator_tone_fit"),
                structure_fit=p.get("curator_structure_fit"),
                theme_fit=p.get("curator_theme_fit"),
                total_fit=p.get("curator_total_fit"),
                tier=p.get("curator_category"),
                is_served=True,
                final_rank=rank,
            )
        )

    # Also log non-served candidates (for debugging why they were filtered)
    for c in candidates:
        if int(c.id) in served_ids:
            continue
        p = c.payload or {}
        evals.append(
            CuratorEvalLog(
                query_id=query_id,
                media_id=int(c.id),
                media_type=media_type,
                title=p.get("title"),
                genre_fit=p.get("curator_genre_fit"),
                tone_fit=p.get("curator_tone_fit"),
                structure_fit=p.get("curator_structure_fit"),
                theme_fit=p.get("curator_theme_fit"),
                total_fit=p.get("curator_total_fit"),
                tier=p.get("curator_category"),
                is_served=False,
                final_rank=None,
            )
        )

    # Log curator evaluations
    if evals:
        try:
            await logger.log_curator_evaluations(evals)
        except Exception as e:
            print(f"[curator_logging] Failed to log evaluations: {e}")

    # Determine selection rule based on tier counts
    strong = tier_stats.get("strong_count", 0)
    limit = tier_stats.get("limit", 8)
    if strong >= limit:
        rule = "all_strong"
    elif strong >= 5:
        rule = "strong_only"
    elif 3 <= strong <= 4:
        rule = "strong_plus_2_moderate"
    elif strong in (1, 2):
        rule = "strong_plus_4_moderate"
    else:
        rule = "moderate_only"

    # Log tier summary
    try:
        await logger.log_tier_summary(
            TierSummaryLog(
                query_id=query_id,
                total_candidates=tier_stats.get("total_candidates", 0),
                strong_count=tier_stats.get("strong_count", 0),
                moderate_count=tier_stats.get("moderate_count", 0),
                no_match_count=tier_stats.get("no_match_count", 0),
                served_count=tier_stats.get("served_count", 0),
                selection_rule=rule,
                curator_latency_ms=tier_stats.get("curator_latency_ms"),
                tier_latency_ms=tier_stats.get("tier_latency_ms"),
            )
        )
    except Exception as e:
        print(f"[curator_logging] Failed to log tier summary: {e}")