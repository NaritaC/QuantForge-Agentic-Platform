# Data contracts

## Canonical daily bars

Primary key: `(instrument_id, trade_date)`.

| Field | Meaning | Contract |
|---|---|---|
| `instrument_id` | Stable market-qualified ID | `000001.SZ`, never a display name |
| `trade_date` | Exchange trading date | Calendar date, no implicit timezone |
| `open/high/low/close/preclose` | Unadjusted vendor prices in this table | Positive; high/low must bound open/close |
| `volume` | Vendor volume normalized to the documented unit | Non-negative; unit stored in adapter mapping |
| `amount` | Turnover amount in CNY | Non-negative |
| `trade_status` | Tradability observation | `TRADE` or `SUSPENDED` |
| `is_st` | ST state known for that date | Boolean, not today's state backfilled |
| `upper_limit/lower_limit` | Daily permitted price bounds | Upper must not be below lower |
| `price_limit_source` | Per-row provenance for price bounds | Vendor, policy version, or explicit unavailable state |
| `source` | Lineage identifier | Required |
| `ingested_at` | Actual platform receipt time | UTC timestamp |

Duplicates are not resolved by “keep last” because arrival order is not a business rule. They fail the quality gate and require source-specific reconciliation.

Daily price limits may be null when a source does not supply them. This is a visible warning and prevents the execution simulator from claiming exact limit-blocked fills. Derived limits must identify a versioned historical policy in `price_limit_source`; they are never silently inferred from today's board rules.

## Financial PIT contract

The Curated financial schema will preserve `period_end`, `announcement_time`, `actual_announcement_date`, `source_available_at`, `ingested_at`, `known_from`, `known_to`, `revision_id`, `statement_type`, `source`, and `checksum`.

When only an announcement date is known, `known_from` is the next exchange trading day. A correction creates a new version and closes the old version's `known_to`; it never overwrites history. Historical vendor downloads are labeled reconstructed PIT rather than pretending the platform captured them at the original date.

## Reference data

The trade calendar contains one row for every calendar date with an explicit `is_trading_day` flag. The security master preserves market-qualified identity, display name, listing date, delisting date, vendor type/status codes, source, and actual ingestion timestamp. Current vendor status is never backfilled as historical truth; dynamic-universe activity is reconstructed from effective listing and delisting dates.

## Research artifact contract

A successful experiment stores seven checksummed Parquet artifacts under its run directory:

| Artifact | Grain | Required evidence |
|---|---|---|
| `universe` | rebalance date × instrument | lifecycle, ST state, liquidity observations/rank |
| `factors` | signal date × eligible instrument | raw factors, transformed factors, rank |
| `signals` | signal date × selected instrument | target weight and signal availability date |
| `orders` | order attempt | signal/scheduled/attempt dates, side, quantity, status, reason |
| `fills` | successful fill | next-open price, fill price, costs, slippage, quantity |
| `holdings` | date × held instrument | quantity, close, and market value |
| `nav` | trading date | cash, market value, equity, NAV, daily return |

`experiment.json` binds those artifacts to the input snapshot, code version, research parameters,
leakage controls, limitations, and metrics. A signal formed at period-end close cannot be attempted
before the next trading-day open. Suspended, limit-blocked, missing-quote, and missing-limit states
are explicit order outcomes; they are never converted into silent fills.
