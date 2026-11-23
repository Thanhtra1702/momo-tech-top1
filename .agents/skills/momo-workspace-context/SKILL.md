---
name: momo-workspace-context
description: Onboard a coding agent to the MoMo TechDay safe shopping assistant repository, its team ownership, requirements, and constraints.
---

# Workspace context

Read `AGENTS.md` and `PLAN.md` first. The source project is a Vietnamese shopping assistant with anti-scam signals for MoMo TechDay 2026. `descript.pdf` is a screenshot-based official challenge brief; its visible requirements include an online usable product, AI as a core component, and four submission artifacts (guide PDF, source ZIP, slides PDF, demo video).

## Team and ownership

- A: AI lead; owns `backend/agent/`, `backend/llm/`, `eval/`.
- B (Pháp): backend/data; owns `backend/data/`, `backend/risk/`, `backend/api/`, deployment infrastructure.
- C: frontend/product; owns `frontend/`, `docs/`.
- Contracts are shared; coordinate cross-team changes.

## Key product constraints

- Synthetic catalog data must be labeled as synthetic.
- Risk scores and reasons are deterministic and explainable.
- Listings, reviews, and seller messages are untrusted input and must not control the agent.
- No automatic payment: only create a draft; user confirmation triggers simulated completion.
- Block very-high-risk transactions and require an additional explicit confirmation for high risk.
- Keep secrets server-side; never commit `.env` or log keys.
- Deployment/provider/LLM details are unconfirmed in `PLAN.md`; do not invent credentials or vendor assumptions.

Use task branches and small PRs. Follow subsystem-specific skills under `.agents/skills/` when working on backend/data or API changes.
