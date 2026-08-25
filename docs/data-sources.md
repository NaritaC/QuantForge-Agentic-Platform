# Data-source roles

## BaoStock: zero-cost baseline

The Day-2 adapter uses [BaoStock](https://www.baostock.com/) 0.9.3 (BSD-licensed SDK) without credentials. It requests unadjusted daily bars (`adjustflag=3`) and preserves the returned vendor-shaped CSV as content-addressed Raw before any normalization. Adjustment semantics are kept separate and will follow the provider's [official adjustment-factor guide](https://www.baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf).

Available fields used here include date, code, OHLC, previous close, volume, amount, adjustment mode, turnover, trading status, percentage change, and historical ST status. Trade-calendar and security-basic queries are exposed by the same adapter.

BaoStock does not return daily upper/lower bounds in this response. The adapter therefore defaults to explicit nulls. A separately enabled `derived_exchange_rules` mode calculates mature-security bounds from previous close, board, date, and historical ST state using a versioned policy and half-up fen rounding. It leaves a conservative 30-calendar-day post-listing window unavailable. These values are sufficient for a functional real-data loop, but exceptional sessions must be cross-checked against AmazingData snapshot limits before results are treated as research evidence.

The versioned policy follows official board rules, including the 2020-08-24 ChiNext change and the 2026-07-06 main-board risk-warning change. Twenty-percent boards are evaluated before ST state because risk-warning stocks on ChiNext and STAR retain their board-level 20% limit. References: [SSE trading rules](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml), [SZSE 2026 rules notice](https://www.szse.cn/lawrules/rule/trade/current/t20260424_620190.html), [SZSE ChiNext Q&A](https://investor.szse.cn/index/update/t20200807_580310.html), and [BSE trading rules](https://www.bse.cn/jygl_list/200028217.html).

## Cross-source policy

- BaoStock is the reproducible default, not an unquestioned authority.
- Tushare basic access will validate selected unadjusted closes and security metadata when the user's points allow it.
- AmazingData trial will be an optional licensed adapter and stronger source for point-in-time financial revisions, snapshots, price limits, and vendor-grade lineage.
- AKShare is a fallback connector. An AKShare endpoint and a direct endpoint backed by the same upstream website are not independent votes.
- Exchange and CNINFO disclosures anchor authoritative identifiers, corporate actions, and announcement facts where practical.

Conflicts are evaluated only after mapping units, adjustment modes, timestamps, and field definitions. The system uses field authority and tolerances, then quarantines unresolved differences; it never chooses a value by majority vote.

No third-party payload is committed to this public repository. API code licenses and the data provider's usage terms are tracked separately.
