# ADR-004: Close the functional research loop before baseline comparison

- Status: accepted
- Date: 2026-08-25

## Context

An ingestion pipeline and a dashboard do not constitute a quantitative research platform. The
system must prove that one versioned input can travel through deterministic research decisions and
portfolio accounting, with every intermediate result available for inspection. Strategy
outperformance is a separate question and should not block verification of the workflow itself.

## Decision

The current milestone is accepted only when one command materializes this chain:

```text
acquire -> normalize -> quality -> universe -> factors -> signals
        -> orders -> fills -> holdings -> NAV -> metrics -> experiment manifest
```

The functional demo uses explicitly synthetic weekday data with valid price limits. It uses the
frozen price-factor definitions—12-1 momentum and 60-day low volatility—but does not fabricate PIT
ROA data. The production three-factor protocol remains unchanged and will activate ROA only after a
versioned financial-fact source satisfies the PIT contract.

Signals are formed on period-end close-known data. Orders are first attempted at the next trading
day's open. The simulator applies board-lot rounding, commission, minimum commission, sell-side
stamp duty, slippage, suspension checks, price-limit checks, and bounded retries. Every attempt and
fill is retained.

## Explicit non-goals for this milestone

- no claim that the demonstration strategy is profitable;
- no parameter selection based on output performance;
- no comparison with buy-and-hold, grid trading, or periodic investment;
- no live trading or broker order placement;
- no substitution of synthetic output for real research evidence.

The experiment manifest records baseline comparison as `deferred` so the omission is visible and
machine-readable.

## Consequences

- `quantforge experiment --config configs/research-demo.yaml` is the offline acceptance command.
- A successful run produces checksummed universe, factor, signal, order, fill, holding, and NAV
  Parquet files plus `metrics.json` and `experiment.json`.
- The visual console reads those artifacts; it does not calculate an alternative result.
- Real-data experiments require canonical daily bars, a trade calendar, a security master, and
  price-limit fields. Missing execution constraints cannot be silently ignored.
