from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from reelix_core.types import UserTasteContext
from reelix_ranking.types import Candidate, ScoreTrace
from reelix_agent.core.types import (
    AgentBaseModel,
    AgentMode,
    ExploreAgentInput,
    RecQuerySpec,
)
from reelix_agent.orchestrator.orchestrator_prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    build_orchestrator_user_prompt,
    build_session_memory_message,
)


class AgentState(AgentBaseModel):
    """State container for the orchestrator agent.

    This holds all state for a single agent turn, including:
    - User/session identifiers
    - LLM conversation messages
    - Domain state (candidates, recommendations, etc.)
    - Telemetry and traces
    """

    # IDs / metadata
    user_id: str
    query_id: str
    session_id: str
    media_type: str
    device_info: Any | None = None

    # LLM conversational state
    messages: list[dict[str, Any]] = Field(default_factory=list)
    session_memory: dict[str, Any] | None = None
    seen_media_ids: list[int] = Field(default_factory=list)
    prior_spec: RecQuerySpec | None = None
    slot_map: dict[str, Any] | None = None

    # Current turn routing + output
    turn_mode: AgentMode | None = None  # value: "recs" | "chat"
    turn_kind: str | None = None  # "new" | "refine" | "chat"
    turn_memory: dict | None = None
    turn_message: str | None = None

    # Domain state
    user_context: UserTasteContext | None = None
    query_spec: RecQuerySpec | None = None
    user_text: str | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    curator_opening: str | None = None
    curator_eval: list = Field(default_factory=list)
    final_recs: list[Candidate] = Field(default_factory=list)
    current_year: int

    # Control
    step_count: int = 0
    max_steps: int = 3  # Maximum turns. Reserved for multiple tool calls per turn
    done: bool = False

    # Telemetry / traces
    ctx_log: dict[str, Any] | None = None
    pipeline_traces: list[dict[int, ScoreTrace]] = Field(default_factory=list)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    tier_stats: dict[str, Any] | None = None  # Curator tier statistics

    @classmethod
    def from_agent_input(
        cls,
        agent_input: ExploreAgentInput,
    ) -> "AgentState":
        """Bootstrap a fresh AgentState from the HTTP-level input.

        Called at the start of an interactive agent run (new query_id), before any tools are invoked.

        Args:
            agent_input: User input for this turn

        Returns:
            Initialized AgentState
        """
        
        # Build the admin/user message contents this turn for orchestrator LLM
        current_year = datetime.now().year
        system_prompt = ORCHESTRATOR_SYSTEM_PROMPT.replace(
            "{{CURRENT_YEAR}}", str(current_year)
        )

        user_msg_content = build_orchestrator_user_prompt(agent_input)
        mem_msg, prior_spec, slot_map = build_session_memory_message(
            agent_input.session_memory
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *([{"role": "system", "content": mem_msg}] if mem_msg else []),
            {"role": "user", "content": user_msg_content},
        ]

        # Pull seen_media_ids from session memory for pipeline exclusion (intent-scoped)
        seen_ids: list[int] = []
        if isinstance(agent_input.session_memory, dict):
            raw = agent_input.session_memory.get("seen_media_ids") or []
            if isinstance(raw, list):
                seen_ids = [
                    int(x)
                    for x in raw
                    if isinstance(x, (int, str)) and str(x).isdigit()
                ]

        return cls(
            user_id=agent_input.user_id,
            query_id=agent_input.query_id,
            session_id=agent_input.session_id,
            media_type=agent_input.media_type.value,
            device_info=agent_input.device_info,
            messages=messages,
            session_memory=agent_input.session_memory,
            prior_spec=prior_spec,
            slot_map=slot_map,
            seen_media_ids=seen_ids,
            user_text=agent_input.query_text,
            current_year=current_year,
        )
