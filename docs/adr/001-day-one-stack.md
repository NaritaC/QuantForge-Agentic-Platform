# ADR-001: Day-one deterministic data stack

- Status: Accepted
- Date: 2026-08-25

## Context

The one-week MVP must be runnable, explainable in a data-engineering interview, and extensible without carrying two equivalent implementations. The immediate workload is daily A-share data on one developer machine, not distributed event processing.

## Decision

Use Python 3.12, pandas as the sole DataFrame framework, PyArrow/Parquet for immutable analytical snapshots, DuckDB for local SQL, PyYAML for explicit configuration, and pytest for verification. Use `src/` packaging and a standard-library CLI.

Raw files are content-addressed and append-only. Staging and Curated outputs are immutable Parquet snapshots. DuckDB queries Parquet directly; it is not yet a stateful application database.

## Consequences

- pandas matches the target job's expected Python analysis ecosystem and reduces first-week integration risk.
- Parquet plus DuckDB makes schema, columnar storage, partitioning, and SQL visible without operating a server.
- Polars, PostgreSQL, ClickHouse, orchestration services, Docker, and C++ are deferred until a measured workload justifies them.
- A future adapter can replace the fixture without changing downstream contracts.

