from reelix_agent.core.llm import call_llm_with_tools
from reelix_agent.core.types import (
    InteractiveAgentInput,
    InteractiveAgentResult,
    AgentMode,
    LlmDecision,
    RecQuerySpec,
)
from reelix_agent.orchestrator.agent_rec_runner import AgentRecRunner
from reelix_agent.orchestrator.agent_state import AgentState
from reelix_llm.client import LlmClient

TERMINAL_TOOLS = {"recommendation_agent"}


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