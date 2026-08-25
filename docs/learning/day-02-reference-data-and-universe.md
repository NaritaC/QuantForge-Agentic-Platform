# Day 02 learning: reference data and dynamic universe

Target time: 60 minutes. The goal is to explain why a quant data engineer cannot select historical stocks from today's constituent list.

## 0–15 min: terms and semantics

- **Security master**: stable instrument identity plus listing/delisting lifecycle; a display name is an attribute, not a key.
- **Trading calendar**: explicit exchange-open flags. “120 trading days” is not `date + 120 days`.
- **Point in time (PIT)**: a query at time `t` may use only records effective and known by `t`.
- **Survivorship bias**: failed and delisted securities disappear when today's list is backfilled.
- **Liquidity proxy**: daily amount is price multiplied by traded quantity in currency units; units must be normalized before comparing sources.
- **Coverage**: valid observations divided by expected market days. A missing vendor row is not automatically a suspension.

Listing age at rebalance date `t` is:

\[
Age_i(t)=\#\{d\in Calendar_{trade}: list\_date_i\le d\le t\}
\]

The liquidity score is:

\[
Liquidity_i(t)=\frac{1}{N_i}\sum_{d\in W_{60}(t)}Amount_{i,d},\qquad N_i\ge48
\]

## 15–30 min: SQL formulation

The important SQL pattern is “filter by as-of time, aggregate a trailing window, join effective master data, then rank the cross-section.”

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

`:minimum_list_date` must come from the 120th prior exchange trading day, not ordinary date arithmetic.

## 30–50 min: Python implementation review

Read `src/quantforge/research/universe.py` and identify these safeguards:

1. Required-column checks stop schema drift early.
2. Duplicate instrument/date rows are rejected rather than silently kept.
3. Rebalance dates must be actual trading days.
4. Listing age is counted from the exchange calendar.
5. The ST state must exist at the rebalance close.
6. Suspended instruments remain visible for the execution simulator.
7. Liquidity ties use `instrument_id` so results are deterministic.
8. Date columns are normalized again after Parquet loading; storage round trips can expose types that an in-memory fixture did not.

Run the focused test:

```powershell
python -m pytest tests/unit/test_universe.py -q
```

## 50–60 min: interview drill

**Why not use CSI 300 constituents downloaded today?**

Because historical membership changes. Backfilling today's survivors removes delisted and underperforming names and creates survivorship bias. Reconstruct membership or build an as-of rules-based universe.

**Why is a suspension not the same as missing data?**

A suspension is an observed market state; missing data may be a vendor or pipeline failure. Mapping both to zero return or zero amount hides outages and biases volatility/liquidity.

**Why use both a 60-day window and a 48-observation threshold?**

The window defines the economic horizon. The threshold is a data-coverage guard that prevents a sparse history from receiving an unstable score.

**Why retain a suspended stock in the universe?**

Universe eligibility and execution feasibility are separate states. Deleting it would invent a liquidation or avoid a position that the strategy might be unable to exit.
