"""
LLM utility functions for the agent system.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from reelix_agent.core.types import LlmDecision

if TYPE_CHECKING:
    from reelix_agent.orchestrator.agent_state import AgentState
    from reelix_core.llm_client import LlmClient


class LlmUsage:
    """Token usage from LLM call."""

    def __init__(
        self,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
    ):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model


async def call_llm_with_tools(
    state: "AgentState",
    llm_client: "LlmClient",
    tools: list[dict[str, Any]] | None = None,
) -> tuple[LlmDecision, LlmUsage]:
    """
    Call the LLM with the current AgentState.messages and tool definitions.
    Mutates `state.messages` by appending the assistant message returned by the LLM.

    Args:
        state: AgentState containing conversation messages
        llm_client: LLM client for API calls
        tools: Optional list of tool definitions in OpenAI format.
               If not provided, imports from orchestrator_prompts (legacy behavior).

    Returns:
        Tuple of (LlmDecision, LlmUsage) - decision and token usage info.
    """

    # 1) Prepare messages for the model.
    messages: list[dict[str, Any]] = state.messages

    # 2) Call LLM client with tools.
    resp = await llm_client.chat(
        messages=messages,
        tools=tools,
        tool_choice="auto",
        model="gpt-4.1-mini",
    )

    # 3) Extract the assistant message from the response.
    choice = resp.choices[0]
    msg = choice.message

    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": msg.content,
    }

    if getattr(msg, "tool_calls", None):
        # OpenAI-style tool_calls attribute
        tool_calls_payload = []
        for tool_call in msg.tool_calls:
            tool_calls_payload.append(
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )
        assistant_msg["tool_calls"] = tool_calls_payload

    state.messages.append(assistant_msg)

    # 4) Extract token usage from response
    usage = getattr(resp, "usage", None)
    llm_usage = LlmUsage(
        input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        model="gpt-4.1-mini",
    )

    # 5) Normalize into LlmDecision.

    # == Case 1: there is at least one tool call ==
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        first_call = tool_calls[0]
        tool_name = first_call.function.name
        raw_args = first_call.function.arguments or "{}"
        tool_call_id = getattr(first_call, "id", None)
        try:
            parsed_args = json.loads(raw_args)
        except json.JSONDecodeError:
            parsed_args = {}

        return (
            LlmDecision(
                is_tool_call=True,
                tool_name=tool_name,
                tool_args=parsed_args,
                content=None,
                tool_call_id=tool_call_id,
            ),
            llm_usage,
        )

    # == Case 2: normal final answer (no tool calls) ==
    content = msg.content or ""
    return (
        LlmDecision(
            is_tool_call=False,
            content=content,
            tool_name=None,
            tool_args={},
        ),
        llm_usage,
    )
