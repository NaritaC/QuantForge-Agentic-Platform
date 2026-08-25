from datetime import UTC, datetime

import pandas as pd

from quantforge.data.normalize import normalize_daily_bars, normalize_instrument_id


def test_normalize_instrument_id_supports_common_vendor_formats() -> None:
    assert normalize_instrument_id("600000") == "600000.SH"
    assert normalize_instrument_id("000001") == "000001.SZ"
    assert normalize_instrument_id("sh.600000") == "600000.SH"
    assert normalize_instrument_id("000001.sz") == "000001.SZ"


def test_normalize_daily_bars_preserves_suspension_as_explicit_state() -> None:
    vendor = pd.DataFrame(
        [
            {
                "symbol": "000001",
                "trade_date": "2024-01-04",
                "open": "9.66",
                "high": "9.66",
                "low": "9.66",
                "close": "9.66",
                "preclose": "9.66",
                "volume": "0",
                "amount": "0",
                "tradestatus": "0",
                "is_st": "0",
                "upper_limit": "10.63",
                "lower_limit": "8.69",
            }
        ]
    )
    ingested_at = datetime(2024, 1, 9, tzinfo=UTC)

    result = normalize_daily_bars(vendor, source="fixture", ingested_at=ingested_at)

    assert result.loc[0, "instrument_id"] == "000001.SZ"
    assert result.loc[0, "trade_status"] == "SUSPENDED"
    assert result.loc[0, "volume"] == 0.0
    assert result.loc[0, "price_limit_source"] == "vendor"
    assert str(result["ingested_at"].dtype) == "datetime64[us, UTC]"
