"""
Default tool registry factory.
"""

from reelix_agent.tools.registry import ToolRegistry
from reelix_agent.tools.recommendation_tool import recommendation_agent_spec


def build_registry() -> ToolRegistry:
    """Build the default tool registry with all available tools.

    Returns:
        ToolRegistry with all registered tools.
    """
    registry = ToolRegistry()

    # Register recommendation_agent (terminal tool)
    registry.register(recommendation_agent_spec)

    # Reserved for future tools here:

    return registry
