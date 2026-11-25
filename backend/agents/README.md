# Agent runtime package

This package contains the assistant runtime, separate from FastAPI routes and domain services under `app/`.

- `prompts.py`: system and deep-reasoning prompts.
- `orchestrator.py`: per-user sessions, prompt construction, the bounded LLM/tool loop, and SSE event generation.
- `tools.py`: LLM-facing tool schemas, argument handling, execution adapters, and UI-block formatting.
- Domain capabilities remain in `app/` (catalog, orders, memory, trips and other business services); tool adapters call these services.

The HTTP layer in `app/main.py` owns authentication, request validation, rate/cost guards, persistence, and streaming transport. It imports the runtime from `agents.orchestrator`. `app/agent.py` and `app/tools.py` are compatibility shims for existing scripts/tests; new imports should use the `agents` package.

When packaging the backend, include both `app/` and `agents/`. The production Dockerfile does this explicitly.
