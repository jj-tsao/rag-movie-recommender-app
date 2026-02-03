from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import Field, field_validator
from dataclasses import dataclass


from pydantic import BaseModel, ConfigDict
from reelix_core.types import MediaType
from reelix_ranking.types import Candidate


class AgentBaseModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ExploreAgentInput(AgentBaseModel):
    user_id: str
    query_id: str
    session_id: str
    media_type: MediaType
    query_text: str
    session_memory: dict | None
    batch_size: int = 20
    device_info: Any | None = None


class RecAgentResult(AgentBaseModel):
    mode: AgentMode
    message: str | None = None
    query_spec: RecQuerySpec | None
    candidates: list[Candidate] = Field(default_factory=list)
    final_recs: list[Candidate] = Field(default_factory=list)
    summary: str | None = None
    turn_memory: dict | None = None
    ctx_log: dict | None = None
    pipeline_traces: list[dict] = Field(default_factory=list)
    agent_trace: list[dict] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    tier_stats: dict | None = None  # Curator tier statistics


class AgentMode(StrEnum):
    RECS = "recs"
    CHAT = "chat"


class RecQuerySpec(BaseModel):
    query_text: str  # raw NL query / vibes
    media_type: MediaType = MediaType.MOVIE
    seed_titles: list[str] = Field(default_factory=list)
    core_genres: list[str] = Field(default_factory=list)
    exclude_genres: list[str] = Field(default_factory=list)
    sub_genres: list[str] = Field(default_factory=list)
    core_tone: list[str] = Field(default_factory=list)
    narrative_shape: list[str] = Field(default_factory=list)
    key_themes: list[str] = Field(default_factory=list)
    providers: list[str] = Field(
        default_factory=list
    )  # canonical service names, e.g. ["netflix", "hulu"]
    year_range: tuple[int, int] | None = None
    # query_filters: QueryFilter | None = None
    max_runtime_minutes: int | None = None
    num_recs: int = 8

    @field_validator(
        "seed_titles",
        "core_genres",
        "exclude_genres",
        "sub_genres",
        "core_tone",
        "narrative_shape",
        "key_themes",
        "providers",
        mode="before",
    )
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        if value is None:
            return []
        return value


class LlmDecision(AgentBaseModel):
    is_tool_call: bool
    content: str | None = None
    tool_name: str | None = None  # function name if is_tool_call=True
    tool_args: dict[str, Any] = {}  # parsed JSON args if is_tool_call=True
    tool_call_id: str | None = None  # id for the tool call (OpenAI API)


@dataclass(frozen=True)
class OrchestratorPlan:
    mode: AgentMode
    decision: LlmDecision | None
    opening_summary: str | None
    message: str | None


class PromptsEnvelope(BaseModel):
    model: str
    params: dict[str, Any] = Field(
        default_factory=dict
    )  # temp/top_p/seed/max_tokens, etc.
    recipe: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(
        default_factory=lambda: {"format": "jsonl", "schema_version": "1"}
    )
    calls: list["LLMCall"] = Field(
        default_factory=list
    )  # one or many calls with caching
    prompt_hash: str  # sha256 of (mode, calls.messages, model, params)
    created_at: float


class LLMCall(BaseModel):
    call_id: int | None
    messages: list[
        dict[str, Any]
    ]  # [{"role":"system","content":...}, {"role":"user","content":...}] pair
    items_brief: list[dict[str, Any]] = Field(
        default_factory=list
    )  # [{"media_id","title"}, ...] (for logs)
