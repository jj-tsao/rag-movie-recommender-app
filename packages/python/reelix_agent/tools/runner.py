"""
Tool runner for executing tools from the registry.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from reelix_agent.tools.registry import ToolRegistry
from reelix_agent.tools.types import ToolContext, ToolResult

if TYPE_CHECKING:
    from reelix_agent.core.types import LlmDecision


class ToolRunner:
    """Executes tools from the registry.

    Responsibilities:
    - Validate tool exists in registry
    - Execute handler with timing/tracing
    - Handle errors gracefully
    - Provide terminal tool lookup for orchestrator flow control
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def run(
        self,
        *,
        decision: "LlmDecision",
        ctx: ToolContext,
    ) -> ToolResult:
        """Execute a tool based on LLM decision.

        Args:
            decision: LlmDecision with tool_name and tool_args
            ctx: ToolContext with dependencies

        Returns:
            ToolResult with success/error status and payload
        """
        tool_name = decision.tool_name
        tool_args = decision.tool_args or {}

        if not tool_name:
            return ToolResult.error(
                "Missing tool name in LlmDecision",
                tool_name=tool_name,
                args=tool_args,
            )

        # 1) Lookup tool
        spec = self._registry.get(tool_name)
        if spec is None:
            return ToolResult.error(
                f"Unknown tool: '{tool_name}'",
                tool_name=tool_name,
                args=tool_args,
            )

        if spec.handler is None:
            return ToolResult.error(
                f"Tool '{tool_name}' has no handler",
                tool_name=tool_name,
            )

        # 2) Execute with timing
        start = time.perf_counter()
        try:
            result = await spec.handler(ctx, tool_args)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return ToolResult.error(
                str(e),
                tool_name=tool_name,
                elapsed_ms=elapsed_ms,
                exception_type=type(e).__name__,
            )

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 3) Enrich metadata
        result.metadata["tool_name"] = tool_name
        result.metadata["elapsed_ms"] = elapsed_ms
        result.metadata["category"] = spec.category.value

        return result

    def is_terminal(self, tool_name: str) -> bool:
        """Check if a tool is terminal (ends orchestrator turn)."""
        return tool_name in self._registry.terminal_tools()

    @property
    def registry(self) -> ToolRegistry:
        """Access the underlying registry."""
        return self._registry
