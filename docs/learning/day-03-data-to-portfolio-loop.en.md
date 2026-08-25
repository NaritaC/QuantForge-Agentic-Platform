# Day 03: The complete data-to-portfolio research loop

> Time budget: 60 minutes. The goal is not to prove that the strategy works. It is to explain why every intermediate artifact exists, how look-ahead is prevented, and how the portfolio is reconciled.

## 1. What runs today

```text
Raw → Staging → Quality → Universe → Factors → Signals
    → Orders → Fills → Holdings → NAV → Metrics
```

Run:

```powershell
python -m quantforge experiment --config configs/research-demo.yaml
python -m quantforge dashboard
```

The deterministic synthetic data proves the engineering path only. It is not strategy evidence. Buy-and-hold, grid-trading, and periodic-investment comparisons are explicitly deferred.

## 2. Interview vocabulary

| Term | Meaning in this project |
|---|---|
| data lineage | Links the request, hashes, field rules, code version, and output snapshots |
| row reconciliation | Input/output row counts at each layer; every non-zero delta needs a rule |
| point-in-time universe | Uses only lifecycle, ST, and liquidity state known on the rebalance date |
| signal availability | A month-end signal is known after close and cannot trade at the same day's open |
| target weight | The intended post-rebalance fraction of portfolio equity |
| order vs. fill | Trading intent and actual execution are separate fact tables |
| portfolio accounting | Daily conservation of cash, holdings value, fees, and equity |
| look-ahead bias | Historical use of data that was not yet knowable at that time |

## 3. Factor formulas

### 12-1 momentum

Skip the most recent 21 trading days and compare with 252 trading days ago:

\[
MOM_{i,t}=\frac{P_{i,t-21}}{P_{i,t-252}}-1
\]

The skip commonly reduces short-term reversal exposure. The implementation is
`quantforge.research.factors.compute_price_factors`.

### 60-day low volatility

\[
r_{i,t}=\frac{P_{i,t}}{P_{i,t-1}}-1,
\qquad
LOWVOL_{i,t}=-\sqrt{\frac{1}{N}\sum_{k=0}^{N-1}(r_{i,t-k}-\bar r)^2}
\]

The negative sign makes lower volatility a higher factor value.

### Cross-sectional MAD winsorization and z-score

\[
MAD_t=median_i(|x_{i,t}-median_i(x_{i,t})|)
\]

Clip to `median ± 5 × MAD`, then standardize:

\[
z_{i,t}=\frac{x^{clip}_{i,t}-mean_i(x^{clip}_{i,t})}{std_i(x^{clip}_{i,t})}
\]

The demonstration equally averages the two price-factor z-scores. It does not fabricate PIT ROA. ROA is activated only after financial facts satisfy announcement-time and revision contracts.

## 4. Why signals, orders, and fills are separate

- `signals`: target weights known after period-end close.
- `orders`: next-open intentions and retries; status may be `filled`, `retry_pending`, `expired`, or `rejected`.
- `fills`: execution facts that actually change cash and holdings.

A suspended, limit-blocked, or missing-quote order cannot silently become a fill. The current protocol retries for at most five trading days.

Execution-price illustration:

\[
P^{buy}_{fill}=P_{open}(1+slippage),\qquad
P^{sell}_{fill}=P_{open}(1-slippage)
\]

A buy changes cash by `-(notional + commission)`; a sell changes it by `+(notional - commission - stamp duty)`.

## 5. NAV and reconciliation

At each close:

\[
Equity_t=Cash_t+\sum_i Shares_{i,t}\times Close_{i,t}
\]

\[
NAV_t=\frac{Equity_t}{InitialCash},\qquad
Drawdown_t=\frac{Equity_t}{\max_{s\leq t}Equity_s}-1
\]

The primary engineering checks are not high returns:

1. only fills may change cash and holdings;
2. fees have the correct sign on buys and sells;
3. old holdings outside the new target create sell orders;
4. daily equity equals cash plus marked holdings;
5. every signal date strictly precedes its fill date.

## 6. SQL review

```sql
-- Detect same-day look-ahead execution
SELECT COUNT(*) AS leakage_rows
FROM read_parquet('artifacts/runs/<run_id>/research/fills.parquet')
WHERE trade_date <= signal_date;

-- Inspect order outcomes
SELECT status, reason, COUNT(*) AS attempts
FROM read_parquet('artifacts/runs/<run_id>/research/orders.parquet')
GROUP BY status, reason
ORDER BY attempts DESC;

-- Review NAV coverage
SELECT MIN(trade_date), MAX(trade_date), MIN(nav), MAX(nav)
FROM read_parquet('artifacts/runs/<run_id>/research/nav.parquet');
```

## 7. Twenty-minute code-reading route

1. `research/universe.py`: why the universe is an as-of function.
2. `research/factors.py`: separating time-series windows from cross-sectional transforms.
3. `research/backtest.py`: constraints, costs, and portfolio accounting.
4. `experiment.py`: binding artifacts and hashes to one experiment.

## 8. Interview self-check

1. Why can a month-end signal not execute at that month's opening price?
2. How can `drop_duplicates(keep='last')` hide a quality defect?
3. What evidence is lost when orders and fills share one table?
4. Why can today's index membership not be backfilled into history?
5. How would you prove that future prices cannot change a past factor value?
6. How should missing daily price limits constrain backtest claims?
