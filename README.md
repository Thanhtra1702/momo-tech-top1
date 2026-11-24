# MoMo Safe Shopping Assistant (backend foundation)

This repository currently contains the project plan and contest brief, plus a first backend implementation for Person B (Pháp). The catalog is generated synthetic demo data; it does not represent actual products, merchants, reviews, or fraud findings. Payment confirmation is simulated and never moves money.

## Run locally

Requires Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. SQLite is initialized at `MOMO_DB_PATH` (default `./momo_demo.sqlite3`). Set optional limits with `MOMO_RATE_LIMIT_PER_MINUTE` and `MOMO_DAILY_BUDGET_VND`. `.env.example` lists these names; the app does not load `.env` automatically.

## API slice

- `GET /health`
- `GET /listings/search?query=tai%20nghe&max_price=2000000&category=audio&limit=20`
- `GET /listings/{listing_id}/risk`
- `POST /orders/draft` with `{"listing_id":"listing-0001"}`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/confirm` with `{"second_confirmation":true}` when required
- `POST /risk/analyze-message` with `{"text":"...","url":"https://..."}`

Search includes risky records so the risk engine can be evaluated. Very-high-risk offers cannot become order drafts. High-risk drafts require an explicit second confirmation before simulated completion. Link analysis only inspects text/hostname heuristics and never fetches submitted URLs.

## Current limitations and integration notes

- The catalog has 300 deterministic records and a 22.2% synthetic positive label ratio, created on first database initialization.
- Risk features and thresholds live in `backend/risk/weights.json`; numeric scores and levels are rule-derived.
- Rate limiting and the illustrative daily budget are process-local, reset on restart/day rollover, and are not multi-instance production controls. The current request budget is a placeholder for future LLM costs; this backend does not call an LLM.
- The demo has no authentication, real payment, external URL reputation lookup, or production database migration layer.
- Stack, hosting, LLM provider/model/budget, and final contracts are marked unconfirmed in `PLAN.md`. Coordinate endpoint/schema changes with A and C before deployment.

## Ownership and context

Read `AGENTS.md` and `.agents/skills/` before coding. Person B owns `backend/data/`, `backend/risk/`, `backend/api/`, and deployment infrastructure. See `PLAN.md` for task mapping and acceptance criteria.
