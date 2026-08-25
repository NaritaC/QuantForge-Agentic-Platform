from __future__ import annotations

DAILY_BAR_PRIMARY_KEY = ("instrument_id", "trade_date")

DAILY_BAR_COLUMNS = (
    "instrument_id",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "trade_status",
    "is_st",
    "upper_limit",
    "lower_limit",
    "source",
    "ingested_at",
)

TRADE_STATUSES = frozenset({"TRADE", "SUSPENDED"})
