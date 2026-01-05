
from __future__ import annotations
import re
import json

from reelix_agent.core.llm import call_llm_with_tools
from reelix_agent.core.types import (
    InteractiveAgentInput,
    InteractiveAgentResult,
    OrchestratorPlan,
    AgentMode,
    LlmDecision,
    RecQuerySpec,
)
from reelix_agent.orchestrator.agent_rec_runner import AgentRecRunner
from reelix_agent.orchestrator.agent_state import AgentState
from reelix_llm.client import LlmClient

TERMINAL_TOOLS = {"recommendation_agent"}
MEMORY_RE = re.compile(r"<MEMORY>\s*(.*?)\s*</MEMORY>", re.DOTALL)

def _strip_memory_block(text: str) -> tuple[str, str | None]:
    """
    Returns (cleaned_message, memory_raw_json_or_text)
    If no block exists, memory is None.
    """
    text = text or ""
    m = MEMORY_RE.search(text)
    memory_raw = m.group(1).strip() if m else None

    # remove the whole block if present
    cleaned = MEMORY_RE.sub("", text).strip()

    return cleaned, memory_raw

def _result_from_state(state: AgentState) -> InteractiveAgentResult:
    return InteractiveAgentResult(
        mode=state.turn_mode or AgentMode.RECS,
        # Domain outputs
        query_spec=state.query_spec,
        candidates=state.candidates,
        final_recs=state.final_recs,
        # Memory + traces
        turn_memory=state.turn_memory,
        ctx_log=state.ctx_log,
        pipeline_traces=state.pipeline_traces,
        agent_trace=state.agent_trace,
    )


async def plan_orchestrator_agent(
    *,
    agent_input: InteractiveAgentInput,
    llm_client: LlmClient,
    max_steps: int | None = None,
) -> tuple[AgentState, OrchestratorPlan]:
    """
    Run the orchestrator LLM:
    - CHAT mdoe: return chat message
    - RECS mode: produce a plan with tool call
    """
    state = AgentState.from_agent_input(agent_input)
    state.turn_message = None
    state.turn_mode = None

    if max_steps is not None:
        state.max_steps = max_steps

    while not state.done and state.step_count < state.max_steps:
        state.step_count += 1
        decision = await call_llm_with_tools(state, llm_client=llm_client)
        print(decision)

        # == Non-tool response: CHAT mode ==
        if not decision.is_tool_call:
            state.turn_mode = AgentMode.CHAT
            cotnent_raw = (decision.content or "").strip()
            msg, memory_raw = _strip_memory_block(cotnent_raw)

            mem: dict = {}
            if memory_raw:
                try:
                    parsed = json.loads(memory_raw)
                    if isinstance(parsed, dict):
                        mem.update(parsed)
                except Exception:
                    pass
            mem["last_user_message"] = (state.user_text or "")
            mem["last_admin_message"] = (msg or "")

            state.turn_message = msg
            state.turn_memory = mem
            state.done = True
            return state, OrchestratorPlan(
                mode=state.turn_mode,
                decision=None,
                opening_summary=None,
                message=msg,
            )

        # == Tool call: if terminal, return plan; else execute and continue ==
        tool = decision.tool_name
        if tool in TERMINAL_TOOLS:
            state.turn_mode = AgentMode.RECS
            tool_args = decision.tool_args or {}
            opening = tool_args.get("opening_summary")
            raw_spec = tool_args.get("rec_query_spec") or {}
            state.query_spec = RecQuerySpec(**raw_spec)

            return state, OrchestratorPlan(
                mode=state.turn_mode,
                decision=decision,
                opening_summary=opening if isinstance(opening, str) else None,
                message=None,
            )

        # == Reserve for non-terminal tools ==
        raise RuntimeError(
            f"Unknown non-terminal tool '{tool}' produced by orchestrator. "
        )

    # Fallback: if loop exits unexpectedly, return a safe chat
    msg = "I'm not sure how to proceed. Please try again."
    state.turn_mode = AgentMode.CHAT
    state.turn_message = msg
    state.done = True
    return state, OrchestratorPlan(
        mode=state.turn_mode,
        decision=None,
        opening_summary=None,
        message=msg,
    )


async def execute_orchestrator_plan(
    *,
    state: AgentState,
    plan: OrchestratorPlan,
    agent_rec_runner: AgentRecRunner,
    user_context_service,
    llm_client: LlmClient,
) -> InteractiveAgentResult:
    """
    Execute a previously produced OrchestratorPlan.
    - RECS: executes the recommendation_agent tool call via AgentState.execute_tool_call.
    """
    # == CHAT mode: ==
    if plan.mode == "CHAT":
        return _result_from_state(state)

    # Defensive
    if plan.decision is None:
        state.turn_mode = AgentMode.CHAT
        state.turn_message = plan.message or "I'm not sure how to proceed. Please try again."
        state.done = True
        return _result_from_state(state)

    # == RECS mode: Execute the tool call ==
    await state.execute_tool_call(
        decision=plan.decision,
        agent_rec_runner=agent_rec_runner,
        llm_client=llm_client,
    )

    state.done = True
    return _result_from_state(state)


# async def run_orchestrator_agent(
#     *,
#     agent_input: InteractiveAgentInput,
#     agent_rec_runner: AgentRecRunner,
#     user_context_service,
#     llm_client: LlmClient,
# ) -> InteractiveAgentResult:
#     """
#     Legacy endpoint. Does not return a opening_summary.
#     """
#     state, plan = await plan_orchestrator_agent(
#         agent_input=agent_input,
#         llm_client=llm_client,
#     )
#     return await execute_orchestrator_plan(
#         state=state,
#         plan=plan,
#         agent_rec_runner=agent_rec_runner,
#         user_context_service=user_context_service,
#         llm_client=llm_client,
#     )


async def run_rec_engine_direct(
    agent_input: InteractiveAgentInput,
    spec: RecQuerySpec,
    agent_rec_runner: AgentRecRunner,
    user_context_service,
    llm_client: LlmClient,
    ) -> InteractiveAgentResult:
    state = AgentState.from_agent_input(agent_input)

    tool_args = {
        "rec_query_spec": spec.model_dump(mode="json"),
        "memory_delta": {"turn_kind": "refine", "recent_feedback": "update filter"},
    }
    decision = LlmDecision(
        is_tool_call=True,
        tool_name="recommendation_agent",
        tool_args=tool_args,
        tool_call_id="chip_rerun",
    )

    await state.execute_tool_call(
        decision=decision,
        agent_rec_runner=agent_rec_runner,
        llm_client=llm_client,
    )
    
    state.done=True
    
    return InteractiveAgentResult(
        mode=state.turn_mode or AgentMode.RECS,
        query_spec=state.query_spec,
        candidates=state.candidates,
        final_recs=state.final_recs,
        summary=state.curator_opening or "",
        turn_memory=state.turn_memory,
        ctx_log=state.ctx_log,
        pipeline_traces=state.pipeline_traces,
        agent_trace=state.agent_trace,
    ) 



async def run_orchestrator_agent(
    agent_input: InteractiveAgentInput,
    agent_rec_runner: AgentRecRunner,
    user_context_service,
    llm_client: LlmClient,
) -> InteractiveAgentResult:
    # user_context = await user_context_service.fetch_user_taste_context(
    #     agent_input.user_id, agent_input.media_type
    # )

    state = AgentState.from_agent_input(agent_input)
    state.turn_message = None
    state.turn_mode = None

    # Main loop
    while not state.done and state.step_count < state.max_steps:
        state.step_count += 1

        llm_decision = await call_llm_with_tools(state, llm_client=llm_client)
        print(llm_decision)

        # A) Non-tool response: chat message
        if not llm_decision.is_tool_call:
            state.turn_mode = AgentMode.CHAT
            state.turn_message = (llm_decision.content or "").strip()
            state.done = True
            break

        # B) Tool call
        tool = llm_decision.tool_name
        await state.execute_tool_call(
            decision=llm_decision,
            agent_rec_runner=agent_rec_runner,
            llm_client=llm_client,
        )

        # If tool is terminal, break; otherwise loop again so LLM can react to tool result
        if tool in TERMINAL_TOOLS:
            state.done = True
            break

        # Non-terminal tools: keep looping
        continue

    # CHAT mode: return chat message only
    if state.turn_mode == AgentMode.CHAT:
        return InteractiveAgentResult(mode=state.turn_mode, message=state.turn_message, query_spec=state.query_spec)

    # REC mode: return final slate + traces
    return InteractiveAgentResult(
        mode=state.turn_mode or AgentMode.RECS,
        query_spec=state.query_spec,
        candidates=state.candidates,
        final_recs=state.final_recs,
        summary=state.curator_opening or "",
        turn_memory=state.turn_memory,
        ctx_log=state.ctx_log,
        pipeline_traces=state.pipeline_traces,
        agent_trace=state.agent_trace,
    )