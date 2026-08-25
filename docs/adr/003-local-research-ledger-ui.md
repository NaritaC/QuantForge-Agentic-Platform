# ADR-003: A read-only local research ledger is part of the MVP

- Status: accepted
- Date: 2026-08-25

## Context

Run manifests, quality reports, DuckDB queries, and Parquet snapshots are strong machine
interfaces but poor primary interfaces for a researcher learning the workflow or reviewing an
experiment. The platform needs a visual surface before factor and backtest output accumulates;
otherwise observability becomes an afterthought and users are pushed toward opening JSON files or
ad-hoc notebooks.

## Decision

The MVP includes a bilingual, read-only Streamlit application called **Research Ledger**. It reads
the same immutable run manifests and curated Parquet snapshots used by the deterministic pipeline.
It does not maintain a second database, rewrite source data, run hidden corrections, or become a
quality-gate bypass.

The first slice displays:

- available pipeline runs and their status;
- row counts, instrument counts, and date coverage;
- indexed close-price series and a bounded data preview;
- errors and warnings from main and reference-data quality reports;
- Raw → Staging → Curated identifiers and checksums;
- honest availability states for the universe, factor, and backtest modules.

The UI uses an editorial research-ledger aesthetic rather than a generic administration template.
Chinese and English copy share the same evidence and behavior.

## Evolution path

The UI grows with deterministic research capabilities:

1. operations ledger: ingestion, coverage, quality, lineage;
2. universe inspector: membership reasons, exclusions, and liquidity ranking;
3. factor laboratory: distributions, IC, quantiles, turnover, and leakage checks;
4. backtest review: NAV, drawdowns, holdings, costs, fills, and attribution;
5. experiment comparison: configurations, snapshots, code versions, and frozen OOS boundaries.

Streamlit is appropriate for the single-user local MVP because it is Python-native and keeps the
first interface thin. A separate API and web client should be reconsidered only when multi-user
access, long-running jobs, or independent deployment becomes a demonstrated requirement.

## Consequences

- The dashboard is installed through an optional `ui` dependency group.
- Dashboard data access lives outside rendering code and is tested without a browser.
- Full datasets are never loaded merely to render a table: previews and chart inputs are bounded
  DuckDB queries.
- Generated reports, local data, and run artifacts remain excluded from Git.
