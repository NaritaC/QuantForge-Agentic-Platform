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

TRADE_CALENDAR_COLUMNS = ("trade_date", "is_trading_day", "source", "ingested_at")

SECURITY_MASTER_COLUMNS = (
    "instrument_id",
    "display_name",
    "list_date",
    "delist_date",
    "instrument_type_code",
    "current_status",
    "source",
    "ingested_at",
)
