"""
Tool registry for tool discovery and management.
"""

from __future__ import annotations

from typing import Iterable

from reelix_agent.tools.types import ToolCategory, ToolSpec


class ToolRegistry:
    """Registry for tool discovery and management.

    Responsibilities:
    - Store and retrieve tool specs by name
    - Provide OpenAI-formatted tool definitions for LLM calls
    - Support filtering by category (terminal, intermediate)
    - Enable dynamic tool registration at runtime
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """Register a tool spec.

        Raises:
            ValueError: If tool name already exists or handler is missing.
        """
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' is already registered")
        if spec.handler is None:
            raise ValueError(f"Tool '{spec.name}' must have a handler")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        """Get a tool spec by name, or None if not found."""
        return self._tools.get(name)

    def get_required(self, name: str) -> ToolSpec:
        """Get a tool spec by name, raising if not found."""
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool: '{name}'")
        return spec

    def list_tools(self, category: ToolCategory | None = None) -> list[ToolSpec]:
        """List all tools, optionally filtered by category."""
        if category is None:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.category == category]

    def terminal_tools(self) -> set[str]:
        """Get names of all terminal tools."""
        return {t.name for t in self._tools.values() if t.category == ToolCategory.TERMINAL}

    def openai_tools(self, categories: Iterable[ToolCategory] | None = None) -> list[dict]:
        """Get OpenAI function calling format for all tools.

        Args:
            categories: Optional filter by categories. If None, returns all tools.

        Returns:
            List of tool definitions in OpenAI function format.
        """
        if categories is None:
            tools = self._tools.values()
        else:
            cat_set = set(categories)
            tools = [t for t in self._tools.values() if t.category in cat_set]

        return [t.to_openai_function() for t in tools]

    def mcp_tools(self) -> list[dict]:
        """Get MCP tool format for all tools (future server integration)."""
        return [t.to_mcp_tool() for t in self._tools.values()]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
