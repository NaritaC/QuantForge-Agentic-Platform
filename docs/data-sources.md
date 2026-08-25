# Data-source roles

## BaoStock: zero-cost baseline

The Day-2 adapter uses [BaoStock](https://www.baostock.com/) 0.9.3 (BSD-licensed SDK) without credentials. It requests unadjusted daily bars (`adjustflag=3`) and preserves the returned vendor-shaped CSV as content-addressed Raw before any normalization. Adjustment semantics are kept separate and will follow the provider's [official adjustment-factor guide](https://www.baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf).

Available fields used here include date, code, OHLC, previous close, volume, amount, adjustment mode, turnover, trading status, percentage change, and ST status. Trade-calendar and security-basic queries are exposed by the same adapter. BaoStock does not return the daily upper/lower price bounds in this daily-bar response, so those fields remain null and produce a quality warning.

## Cross-source policy

- BaoStock is the reproducible default, not an unquestioned authority.
- Tushare basic access will validate selected unadjusted closes and security metadata when the user's points allow it.
- AmazingData trial will be an optional licensed adapter and stronger source for point-in-time financial revisions, snapshots, price limits, and vendor-grade lineage.
- AKShare is a fallback connector. An AKShare endpoint and a direct endpoint backed by the same upstream website are not independent votes.
- Exchange and CNINFO disclosures anchor authoritative identifiers, corporate actions, and announcement facts where practical.

Conflicts are evaluated only after mapping units, adjustment modes, timestamps, and field definitions. The system uses field authority and tolerances, then quarantines unresolved differences; it never chooses a value by majority vote.

No third-party payload is committed to this public repository. API code licenses and the data provider's usage terms are tracked separately.
