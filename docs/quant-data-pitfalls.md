# Quant data pitfalls demonstrated by this project

## Duplicate records are semantic conflicts

The daily-bar primary key is instrument plus trade date. Keeping the last duplicate would make filesystem order decide market truth. QuantForge fails the Curated quality gate and retains Raw evidence for reconciliation.

## Missing rows and suspensions are different

A suspension is an observed market state and belongs in the table with `trade_status=SUSPENDED`. A missing row may mean a closed exchange, newly listed instrument, delisting, vendor failure, or pipeline failure. Filling every missing return with zero would turn data outages into artificial low volatility.

## Codes and names are not stable identities

Display names change, and the same numeric code is ambiguous without a venue. Vendor codes are mapped to a market-qualified `instrument_id`; name history will live in a separate effective-dated master table.

## Volume units differ by source

Some APIs report shares while others report lots. Cross-source checks must first normalize documented units. Similar-looking numbers are not comparable merely because their column is called `volume`.

## Adjustment is not “cleaning”

Raw prices are preserved. Total-return features are derived from event-aware adjustment factors known as of the signal date. Overwriting prices with a currently downloaded forward-adjusted series can leak later corporate actions into historical research.

## Report period is not availability time

A 2024-12-31 annual result was not known on that date. The PIT query uses the announcement/revision version visible at the signal time. If no exact publication timestamp exists, the conservative usability time is the next trading day.

## Revisions must not overwrite history

Restatements create a new record version with a new `known_from`. A backtest dated before the correction must still see the older statement. Today's corrected value cannot be backfilled into past decisions.

## Daily data does not require daily rebalancing

Prices, risk, NAV, and tradability are observed daily while slow signals may trade monthly. Confusing data frequency with decision frequency creates excess turnover and cost without adding independent information.

## Signal and execution timestamps must differ

A month-end close can form a signal only after that close exists. The baseline therefore attempts execution at the next trading-day open. Trading at the same close is a look-ahead assumption unless an implementable pre-close protocol is modeled.

## Limit and suspension constraints create path dependence

A target portfolio is not an executed portfolio. Next-open buys at the upper limit and sells at the lower limit are conservatively unfilled when only daily data is available. Orders retry for five trading days; old holdings and unused cash remain real state.

## Today's constituents cause survivorship bias

The research universe will be reconstructed at every rebalance from listing age, ST/delisting state, and trailing liquidity. Backfilling today's index members removes many failed or delisted securities from history.

The implemented universe counts exchange trading days since listing, requires at least 48 valid amount observations in the trailing 60-market-day window, excludes the ST state visible at the rebalance close, and ranks average amount deterministically. A suspended security can remain eligible because inability to execute is portfolio state, not permission to rewrite the research universe.

## Free SDKs can fail operationally

The BaoStock SDK can wait indefinitely if a server connection closes mid-message. QuantForge applies a socket deadline and an EOF guard, keeps batches bounded, and will add checkpointed retries before a full-market download. Network availability is never treated as a data-quality pass.

## In-memory fixtures can hide persisted data types

An all-null `delist_date` column can return from Parquet as `datetime64[ns]`, while a small mixed fixture may behave like Python `date` objects. Comparing them directly fails only after persistence. The research layer normalizes all date-like inputs to midnight pandas timestamps, and a regression test performs an actual Parquet round trip.

## Labels need a purge boundary

The 20-trading-day future-return label overlaps future observations. Walk-forward folds and the frozen final holdout therefore use at least a 20-trading-day purge so training features cannot borrow validation outcomes.
