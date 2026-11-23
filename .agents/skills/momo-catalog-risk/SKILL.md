---
name: momo-catalog-risk
description: Build or update the synthetic product catalog, listing search, and transparent rule-based scam risk scoring.
---

# Catalog and risk workflow

Before edits, read `AGENTS.md`, `PLAN.md` Task 2 and Task 3, plus this skill. B (Pháp) owns `backend/data/` and `backend/risk/`.

## Data contract

Represent products, sellers, listings and reviews separately. Listings include `scam_label` and `scam_type`; include price, product/category, seller trust/age, payment channel, description and review metadata needed by rules. Seed data is deterministic synthetic demo data (target: 300 listings, 20–25% labeled risky); do not claim it is real marketplace data.

## Risk engine

- Scores are integers from 0 to 100, with `low`, `medium`, `high`, and `very_high` levels.
- Keep weights/thresholds in configuration and return concrete reason codes plus human-readable Vietnamese explanations.
- Use price deviation against same-product median, seller age/reputation, repetitive or clustered reviews, off-platform payment, and urgency language.
- Risk levels are derived only from the configured deterministic score. LLMs may extract input signals but cannot set score/level.
- Avoid categorical accusations; describe observed risk indicators.

## Search behavior

Support Vietnamese query text, category and max-price filters, stable ordering, and a bounded result limit. Keep synthetic scam listings discoverable for risk evaluation, but any recommendation/ordering integration must filter/block according to policy.

When changing the contract, coordinate with the agent and UI owners. Keep seed generation deterministic and preserve label proportions.
