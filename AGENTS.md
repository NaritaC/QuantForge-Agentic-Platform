# QuantForge Agent Operating Guide

This repository is an audit-first quantitative research platform. Agents are collaborators above a deterministic core; they are not a source of market truth.

## Product boundary

- The package name is `quantforge`; the product and repository name is `QuantForge-Agentic-Platform`.
- The deterministic pipeline must run with every model and agent disabled.
- Raw market or financial data is append-only and content-addressed.
- Staging normalizes vendor semantics. Curated data must pass explicit contracts and quality gates.
- Point-in-time availability, revisions, lineage, and execution constraints are first-class data.
- Research results are evidence, not return promises.

## Agent permissions

Agents may:

- draft versioned experiment configurations;
- explain structured quality reports;
- propose tests and leakage checks;
- summarize deterministic research outputs;
- edit code and documentation with tests and review.

Agents must not:

- modify or overwrite Raw data;
- invent, repair, or silently impute market facts;
- bypass schema, quality, PIT, risk, test, or deployment gates;
- place orders or handle brokerage credentials;
- publish licensed vendor data, credentials, or private documents;
- select parameters using the frozen final out-of-sample period.

## Engineering rules

- Python 3.12, pandas, PyArrow, DuckDB, pytest; add dependencies only when they serve the current vertical slice.
- Core logic belongs in `src/quantforge`; notebooks are not production implementations.
- Network adapters implement the same contract as the offline fixture adapter and are mockable.
- Never commit `data/`, `.env`, databases, Parquet, PDFs, logs, caches, or generated reports.
- Preserve user changes and avoid destructive Git history operations.
- Run unit, integration, contract, leakage, and idempotency tests before a milestone push.
- Record material architecture decisions in `docs/adr/`.

## Research protocol frozen for the MVP

- Daily A-share data; monthly baseline rebalance and weekly sensitivity check.
- Month-end close forms the signal; next trading-day open is the attempted execution price.
- Suspended or limit-blocked orders retry for at most five trading days.
- Dynamic universe: listed for at least 120 trading days, non-ST, non-delisted, top 300 by trailing 60-day amount.
- Factors: 12-1 momentum, 60-day low volatility, PIT ROA TTM.
- Cross-sectional median ± 5 MAD winsorization followed by z-score; no non-PIT industry backfill.
- 2017 warm-up; 2018-2021 research; 2022/2023/2024 walk-forward folds; 2025-latest frozen final OOS.

