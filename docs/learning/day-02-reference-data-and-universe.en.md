# Day 02 learning: reference data and dynamic universe

[简体中文](day-02-reference-data-and-universe.zh-CN.md) · [Language index](day-02-reference-data-and-universe.md)

Target time: 60 minutes. The goal is to explain why a quant data engineer cannot select historical stocks from today's constituent list and how to construct an auditable point-in-time universe.

## 0–15 min: terms and semantics

- **Security master**: stable instrument identity plus the listing and delisting lifecycle. A display name is an attribute, not a key.
- **Trading calendar**: explicit exchange-open flags. “Listed for 120 trading days” is not `listing date + 120 calendar days`.
- **Point in time (PIT)**: a query at time `t` may use only records effective and known by `t`.
- **Survivorship bias**: failed and delisted securities disappear when today's list is backfilled into history.
- **Liquidity proxy**: daily amount is price multiplied by traded quantity in currency units; units and field definitions must be normalized before comparing sources.
- **Coverage**: valid observations divided by expected market days. A missing vendor row is not automatically a suspension.

Listing age for instrument (i) at rebalance date (t) is:

\[
Age_i(t)=\#\{d\in Calendar_{trade}: list\_date_i\le d\le t\}
\]

The liquidity score is mean amount over the latest 60 market trading days:

\[
Liquidity_i(t)=\frac{1}{N_i}\sum_{d\in W_{60}(t)}Amount_{i,d},\qquad N_i\ge48
\]

The 60-day window defines the economic horizon, while the minimum of 48 valid observations is a separate data-coverage gate.

## 15–30 min: SQL formulation

The central SQL pattern is: filter by as-of time, aggregate a trailing window, join effective security master data and rebalance-date state, and finally rank the cross-section.

```sql
WITH liquidity AS (
    SELECT
        instrument_id,
        avg(amount) AS liquidity_score,
        count(amount) AS observations
    FROM daily_bars
    WHERE trade_date BETWEEN :window_start AND :rebalance_date
    GROUP BY instrument_id
    HAVING count(amount) >= 48
),
state_at_close AS (
    SELECT instrument_id, is_st, trade_status
    FROM daily_bars
    WHERE trade_date = :rebalance_date
),
eligible AS (
    SELECT
        m.instrument_id,
        l.liquidity_score,
        s.trade_status
    FROM security_master AS m
    JOIN liquidity AS l USING (instrument_id)
    JOIN state_at_close AS s USING (instrument_id)
    WHERE m.list_date <= :minimum_list_date
      AND (m.delist_date IS NULL OR m.delist_date > :rebalance_date)
      AND NOT s.is_st
)
SELECT *, row_number() OVER (
    ORDER BY liquidity_score DESC, instrument_id
) AS liquidity_rank
FROM eligible
QUALIFY liquidity_rank <= 300;
```

`:minimum_list_date` must be the 120th previous exchange trading day, not a date produced by ordinary calendar arithmetic.

SQL points to understand:

1. `GROUP BY` reduces daily bars to one liquidity record per instrument.
2. `HAVING` checks observation coverage after aggregation; a pre-aggregation `WHERE` cannot replace it.
3. `JOIN ... USING (instrument_id)` requires every layer to use the same stable identifier.
4. `row_number() OVER (...)` ranks the cross-section without collapsing instrument rows.
5. `instrument_id` is the secondary sort key so ties are deterministic across runs.
6. DuckDB's `QUALIFY` filters a window-function result directly.

## 30–50 min: Python implementation review

Read `src/quantforge/research/universe.py` and identify these safeguards:

1. Required-column checks stop schema drift early.
2. Duplicate instrument/date rows are rejected rather than silently keeping an arbitrary row.
3. Rebalance dates must be actual exchange trading days.
4. Listing age is counted from the exchange calendar instead of a calendar-day difference.
5. The ST state visible at the rebalance close must be present.
6. Suspended instruments remain visible to the execution simulator.
7. Liquidity ties use `instrument_id` so results are deterministic.
8. Date columns are normalized again after Parquet loading; storage round trips can expose types that an in-memory fixture did not.

Run the focused test:

```powershell
python -m pytest tests/unit/test_universe.py -q
```

Suggested code-reading exercises:

- Locate validation for `liquidity_window` and `min_liquidity_observations`.
- Explain why `trade_status == SUSPENDED` is not an exclusion rule.
- Temporarily change `top_n=300` to `top_n=2`, predict the result, and compare it with the test output.
- Add a duplicate primary key to the fixture and observe where the pipeline fails.

## 50–60 min: interview drill

**Question 1: Why not use CSI 300 constituents downloaded today for a backtest ten years ago?**

Historical membership changes. Backfilling today's survivors removes delisted, failed, and removed names and creates survivorship bias. Reconstruct historical membership or build an as-of rules-based universe.

**Question 2: Why is a suspension different from missing data?**

A suspension is an observed market state. Missing data may be a vendor, network, or pipeline failure. Mapping both to zero return or zero amount hides outages and biases volatility and liquidity.

**Question 3: Why use both a 60-day window and a 48-observation threshold?**

The 60-day window defines the economic horizon. The 48-observation threshold is a coverage gate that prevents sparse histories from receiving unstable or incomparable scores.

**Question 4: Why can a suspended stock remain in the research universe?**

Universe eligibility and order feasibility are separate states. Removing the stock would assume the strategy could avoid it in advance or liquidate it when trading was impossible. It should remain visible while the execution layer records unfilled orders, unused cash, or trapped holdings.

**Question 5: What is the difference between mean amount and total amount?**

When all instruments have exactly 60 observations, they produce the same ranking. With unequal coverage, a total systematically favors instruments with more rows. QuantForge uses mean amount and separately requires at least 48 observations.

**Question 6: Why test data after a Parquet round trip?**

Serialization can change the concrete type of null-heavy columns. An entirely null delisting-date column may return as `datetime64[ns]`, while a small in-memory fixture may contain Python `date` objects. A real storage round-trip test reveals this boundary.

## Completion criteria

After this lesson, you should be able to do the following without referring to the document:

1. Write the listing-age and 60-day liquidity formulas.
2. Explain PIT, survivorship bias, coverage, and suspension semantics.
3. Walk through the SQL filters, aggregation, joins, and window ranking.
4. Explain why QuantForge separates universe construction from order execution.
5. Answer at least four interview questions and identify the remaining need for historical full-market data and a checkpointed downloader.

