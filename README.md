# QuantForge Agentic Platform

An audit-first, agent-assisted quantitative data and research platform for A-share daily data.

The central design rule is simple: agents may help researchers, but correctness comes from deterministic data contracts, point-in-time semantics, quality gates, reproducible snapshots, and tests. Disabling every model must leave ingestion, validation, feature computation, backtesting, and reporting functional.

> Status: a deterministic data-to-portfolio research loop plus a local read-only Evidence Console.
> The closed-loop demo is synthetic and proves functionality only; it is not research evidence.

## What runs today

```text
vendor or deterministic demo data
  -> content-addressed Raw + lineage manifest
  -> canonical Staging normalization
  -> explicit passed/failed quality checks
  -> immutable partitioned Parquet snapshot
  -> point-in-time dynamic universe
  -> 12-1 momentum + 60-day low-volatility factors
  -> MAD winsorization + cross-sectional z-score + target weights
  -> next-open orders, fills, fees, holdings, NAV, and metrics
  -> checksummed experiment manifest + visual inspection
```

For BaoStock runs, the same command also materializes canonical trade-calendar and security-master snapshots before research data is used.

The loop explicitly demonstrates stable instrument IDs, suspension state, OHLC validation,
duplicate-key rejection, SHA-256 lineage, idempotent storage, field-level transformations, SQL over
Parquet, no-lookahead signal timing, A-share board lots, transaction costs, and unfilled-order
retries. A BaoStock adapter adds real unadjusted daily bars without credentials; see
[data-source roles](docs/data-sources.md).

## Quick start

Requires Python 3.12.

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m quantforge pipeline --config configs/mvp.yaml

# One-command, offline data-to-portfolio functional loop.
python -m quantforge experiment --config configs/research-demo.yaml

# Optional network smoke test; generated vendor data remains local and ignored.
python -m pip install -e ".[dev,baostock]"
python -m quantforge pipeline --config configs/baostock-smoke.yaml
```

Generated market data and run artifacts stay under `data/` and `artifacts/`; both are intentionally ignored by Git.

### Open the visual Research Ledger

The bilingual local UI reads the exact run and experiment artifacts. It exposes vendor requests,
row reconciliation, processing code references, field mappings, all quality checks, Raw/Curated
comparison, universe, factors, signals, orders, fills, holdings, NAV, metrics, and limitations:

```powershell
python -m pip install -e ".[dev,ui]"
python -m quantforge dashboard
```

The default address is `http://localhost:8501`. The dashboard is deliberately read-only: every
displayed result comes from deterministic artifacts and can be traced to a local run manifest,
snapshot checksum, configuration checksum, and Git commit. See
[ADR-003](docs/adr/003-local-research-ledger-ui.md) and
[ADR-004](docs/adr/004-functional-research-loop.md).

The current loop deliberately does **not** compare performance with buy-and-hold, grid trading, or
periodic investment. Baseline comparison is recorded as `deferred`, rather than being silently
omitted. PIT ROA TTM remains part of the frozen production protocol but is not fabricated for the
price-only synthetic demonstration.

## Research protocol

- Daily data does not imply daily turnover: the baseline is month-end signal formation and next-open execution.
- Weekly rebalance is a sensitivity comparison; frequency is never selected on the frozen test period.
- The dynamic universe uses listing age, ST/delisting state, and trailing liquidity rather than today's index members.
- Financial facts become usable on the next trading day after their actual announcement date when no exact timestamp exists.
- The initial factors are 12-1 momentum, 60-day low volatility, and PIT ROA TTM.
- Suspended and limit-blocked orders remain unfilled and retry for at most five trading days.

See [the data contract](docs/data-contracts.md), [quant-data pitfalls](docs/quant-data-pitfalls.md), and [ADR-001](docs/adr/001-day-one-stack.md).

Credentials are entered only in the local, Git-ignored `.env`; see [the secrets guide](docs/secrets.md). Never put tokens in command arguments or commit them to YAML.

The daily one-hour learning track covers reference data and dynamic-universe construction in
[简体中文](docs/learning/day-02-reference-data-and-universe.zh-CN.md) and
[English](docs/learning/day-02-reference-data-and-universe.en.md), followed by the complete
data-to-portfolio loop in
[简体中文](docs/learning/day-03-data-to-portfolio-loop.zh-CN.md) and
[English](docs/learning/day-03-data-to-portfolio-loop.en.md). Each lesson includes terminology,
formulas, SQL, Python code routes, and interview questions.

## Data-source policy

The zero-cost baseline will use BaoStock, with Tushare basic access, AmazingData trial access, AKShare, exchanges, and CNINFO used only where their field semantics and licenses permit. Sources are compared by lineage, authority, units, adjustment rules, and tolerance—not by majority vote.

No vendor payload, SDK, manual, token, or credential is included in this repository. The AmazingData integration will expose only adapter code, schemas, and mocks because its data is licensed separately.

## License

Platform code is licensed under Apache-2.0. Data obtained through third parties retains its own terms and is not covered by the code license.
