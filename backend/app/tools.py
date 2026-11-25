"""Compatibility imports for tool adapters moved to `backend/agents/tools.py`."""

from agents.tools import (
    TOOL_SPECS,
    TOOLS_BY_NAME,
    Tool,
    ToolContext,
    ToolError,
    ToolResult,
    card,
    compact_for_llm,
    run_tool,
)

__all__ = [
    "TOOL_SPECS",
    "TOOLS_BY_NAME",
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolResult",
    "card",
    "compact_for_llm",
    "run_tool",
]
