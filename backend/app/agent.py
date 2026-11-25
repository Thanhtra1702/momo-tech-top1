"""Backward-compatible import surface for the moved agent runtime.

New runtime code lives under `backend/agents/`; this module remains so existing
API, tests, and scripts that import `app.agent` continue to work.
"""

from agents import orchestrator as _runtime
from agents.orchestrator import (
    SESSION_ID_PATTERN,
    AgentDeps,
    Session,
    SessionStore,
    build_system_prompt,
    run_turn,
)

# Keep the module attribute available for legacy monkeypatches in tests/scripts.
time = _runtime.time

__all__ = [
    "SESSION_ID_PATTERN",
    "AgentDeps",
    "Session",
    "SessionStore",
    "build_system_prompt",
    "run_turn",
]
