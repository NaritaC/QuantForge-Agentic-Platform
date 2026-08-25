# QuantForge Agentic Platform

An audit-first, agent-assisted quantitative data and research platform for A-share daily data.

The central design rule is simple: agents may help researchers, but correctness comes from deterministic data contracts, point-in-time semantics, quality gates, reproducible snapshots, and tests. Disabling every model must leave ingestion, validation, feature computation, backtesting, and reporting functional.

> Status: Day-1 vertical slice. The public fixture is synthetic and must not be interpreted as research evidence.

## What runs today

```text
offline vendor-shaped CSV
  -> content-addressed Raw + lineage manifest
  -> canonical Staging normalization
  -> deterministic data-quality gate
  -> immutable partitioned Parquet snapshot
  -> DuckDB research query
  -> reproducible run manifest
```

For BaoStock runs, the same command also materializes canonical trade-calendar and security-master snapshots before research data is used.

The slice explicitly demonstrates stable instrument IDs, suspension state, OHLC validation, duplicate-key rejection, SHA-256 lineage, idempotent storage, and SQL over Parquet. A BaoStock adapter adds real unadjusted daily bars without requiring credentials; see [data-source roles](docs/data-sources.md).

## Quick start

Requires Python 3.12.

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m quantforge pipeline --config configs/mvp.yaml

# Optional network smoke test; generated vendor data remains local and ignored.
python -m pip install -e ".[dev,baostock]"
python -m quantforge pipeline --config configs/baostock-smoke.yaml
```

Generated market data and run artifacts stay under `data/` and `artifacts/`; both are intentionally ignored by Git.

## Research protocol

- Daily data does not imply daily turnover: the baseline is month-end signal formation and next-open execution.
- Weekly rebalance is a sensitivity comparison; frequency is never selected on the frozen test period.
- The dynamic universe uses listing age, ST/delisting state, and trailing liquidity rather than today's index members.
- Financial facts become usable on the next trading day after their actual announcement date when no exact timestamp exists.
- The initial factors are 12-1 momentum, 60-day low volatility, and PIT ROA TTM.
- Suspended and limit-blocked orders remain unfilled and retry for at most five trading days.

See [the data contract](docs/data-contracts.md), [quant-data pitfalls](docs/quant-data-pitfalls.md), and [ADR-001](docs/adr/001-day-one-stack.md).

Credentials are entered only in the local, Git-ignored `.env`; see [the secrets guide](docs/secrets.md). Never put tokens in command arguments or commit them to YAML.

The daily one-hour learning track starts with [reference data and dynamic-universe construction](docs/learning/day-02-reference-data-and-universe.md), including terminology, formulas, DuckDB SQL, Python review, and interview questions.

## Data-source policy

The zero-cost baseline will use BaoStock, with Tushare basic access, AmazingData trial access, AKShare, exchanges, and CNINFO used only where their field semantics and licenses permit. Sources are compared by lineage, authority, units, adjustment rules, and tolerance—not by majority vote.

No vendor payload, SDK, manual, token, or credential is included in this repository. The AmazingData integration will expose only adapter code, schemas, and mocks because its data is licensed separately.

## License

Platform code is licensed under Apache-2.0. Data obtained through third parties retains its own terms and is not covered by the code license.
