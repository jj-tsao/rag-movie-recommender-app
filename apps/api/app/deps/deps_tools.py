"""
Dependency injection for tool infrastructure.
"""

from typing import cast
from fastapi import Request
from reelix_agent.tools import ToolRegistry, ToolRunner


def get_tool_registry(request: Request) -> ToolRegistry:
    """FastAPI dependency that returns the app's shared ToolRegistry.

    The registry is initialized once at startup in main.py::lifespan().

    Returns:
        ToolRegistry: Shared tool registry instance.

    Raises:
        RuntimeError: If tool_registry not initialized (e.g., REELIX_SKIP_RECOMMENDER_INIT=1).
    """
    registry = getattr(request.app.state, "tool_registry", None)
    if registry is None:
        raise RuntimeError("tool_registry not initialized")
    return cast(ToolRegistry, registry)


def get_tool_runner(request: Request) -> ToolRunner:
    """FastAPI dependency that returns the app's shared ToolRunner.

    The runner is initialized once at startup in main.py::lifespan().

    Returns:
        ToolRunner: Shared tool runner instance.

    Raises:
        RuntimeError: If tool_runner not initialized (e.g., REELIX_SKIP_RECOMMENDER_INIT=1).
    """
    runner = getattr(request.app.state, "tool_runner", None)
    if runner is None:
        raise RuntimeError("tool_runner not initialized")
    return cast(ToolRunner, runner)
