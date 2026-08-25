# ADR-002: Point-in-time dynamic A-share universe

- Status: Accepted
- Date: 2026-08-25

## Context

Using today's index constituents in historical research removes many delisted and failed firms and gives the strategy information that was unavailable at the time. Selecting the entire market without liquidity controls also creates portfolios that cannot be executed realistically.

## Decision

At every rebalance close, construct eligibility from effective-dated security master data, that day's ST state, and observations available through that close. Require at least 120 exchange trading days since listing. Exclude instruments whose delisting date is effective and exclude current ST instruments. Compute mean amount over the latest 60 market trading days, require at least 48 valid amount observations, rank descending, and retain the top 300.

Suspension is not an eligibility deletion. A suspended instrument can remain in the research universe; the execution layer must keep the attempted order unfilled and preserve cash or the old holding. Explicit suspension rows with zero amount reduce liquidity, while genuinely missing vendor observations do not become fabricated zeros.

## Consequences

- The universe is reproducible from data visible at each rebalance instead of an index list downloaded today.
- Listing age uses the exchange calendar, not calendar-day subtraction.
- Mean amount avoids rewarding a stock merely for having more non-missing rows, while the 48-observation floor prevents sparse histories from looking liquid.
- Historical security discovery requires periodic market snapshots and resumable downloads; a fixed 50-stock demonstration sample cannot be presented as the research universe.

