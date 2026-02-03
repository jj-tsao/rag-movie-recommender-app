"""
Reelix Agent Tools Package.

MCP-compatible tool infrastructure for the orchestrator agent.
"""

from reelix_agent.tools.types import (
    ToolCategory,
    ToolContext,
    ToolResult,
    ToolResultStatus,
    ToolSpec,
)
from reelix_agent.tools.registry import ToolRegistry
from reelix_agent.tools.runner import ToolRunner
from reelix_agent.tools.default_registry import build_registry

__all__ = [
    # Types
    "ToolCategory",
    "ToolContext",
    "ToolResult",
    "ToolResultStatus",
    "ToolSpec",
    # Registry & Runner
    "ToolRegistry",
    "ToolRunner",
    # Factory
    "build_registry",
]
