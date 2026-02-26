"""
MCP-compatible tool type definitions.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from reelix_agent.orchestrator.agent_rec_runner import AgentRecRunner
    from reelix_agent.orchestrator.agent_state import AgentState
    from reelix_core.llm_client import LlmClient
else:
    AgentRecRunner = Any
    AgentState = Any
    LlmClient = Any


class ToolCategory(StrEnum):
    """
    Tool execution behavior category.
    """

    TERMINAL = "terminal"  # Ends the orchestrator turn (e.g., recommendation_agent)
    INTERMEDIATE = "intermediate"  # Returns result to LLM for further processing


class ToolResultStatus(StrEnum):
    """Status of a tool execution."""

    SUCCESS = "success"
    ERROR = "error"


class ToolResult(BaseModel):
    """Result of a tool execution.

    MCP-compatible with:
    - payload: the actual result data (maps to MCP's content)
    - is_error: whether execution failed

    Extended with:
    - status: more granular status enum
    - metadata: execution metadata (timing, traces)
    """

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    payload: dict[str, Any] = Field(default_factory=dict)
    is_error: bool = Field(default=False)
    error_message: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def success(cls, payload: dict[str, Any], **metadata: Any) -> ToolResult:
        """Create a successful result."""
        return cls(
            status=ToolResultStatus.SUCCESS,
            payload=payload,
            metadata=metadata,
        )

    @classmethod
    def error(cls, message: str, **metadata: Any) -> ToolResult:
        """Create an error result."""
        return cls(
            status=ToolResultStatus.ERROR,
            is_error=True,
            error_message=message,
            metadata=metadata,
        )

    def to_tool_message(self, tool_call_id: str, tool_name: str) -> dict[str, Any]:
        """Format for LLM tool result message (OpenAI format)."""
        import json

        content = self.payload if not self.is_error else {"error": self.error_message}
        return {
            "role": "tool",
            "name": tool_name,
            "tool_call_id": tool_call_id,
            "content": json.dumps(content) if isinstance(content, dict) else str(content),
        }


# Type alias for tool handler function
ToolHandler = Callable[["ToolContext", dict[str, Any]], Awaitable[ToolResult]]


class ToolSpec(BaseModel):
    """MCP-compatible tool specification.

    Mirrors the MCP Tool type:
    - name: unique identifier
    - description: human-readable description for LLM
    - input_schema: JSON Schema for parameters

    Extended with:
    - category: terminal/intermediate behavior (orchestrator flow control)
    - handler: async function that executes the tool
    """

    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Human-readable description for LLM")
    input_schema: dict[str, Any] = Field(
        ...,
        alias="inputSchema",
        description="JSON Schema object describing tool parameters",
    )
    category: ToolCategory = Field(
        default=ToolCategory.INTERMEDIATE,
        description="Execution behavior category",
    )

    # Handler is not serialized - it's the implementation
    handler: ToolHandler | None = Field(default=None, exclude=True)

    model_config = {"populate_by_name": True}

    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def to_mcp_tool(self) -> dict[str, Any]:
        """Convert to MCP tool format (for future server integration)."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class ToolContext(BaseModel):
    """Execution context passed to tool handlers. Designed for dependency injection.

    Contains all dependencies a tool might need:
    - state: current AgentState (mutable)
    - agent_rec_runner: recommendation pipeline runner
    - llm_client: for tools that need LLM calls (e.g., curator)
    """

    # Runtime aliases to Any avoid circular imports; static types still apply.
    state: AgentState = Field(..., description="AgentState instance")
    agent_rec_runner: AgentRecRunner = Field(..., description="AgentRecRunner instance")
    llm_client: LlmClient = Field(..., description="LlmClient instance")

    # Extensible metadata for future needs
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def user_id(self) -> str:
        """Get user ID from state."""
        return self.state.user_id

    @property
    def query_id(self) -> str:
        """Get query ID from state."""
        return self.state.query_id

    @property
    def session_id(self) -> str | None:
        """Get session ID from state."""
        return self.state.session_id
