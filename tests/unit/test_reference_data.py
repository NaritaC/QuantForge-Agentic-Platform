from datetime import UTC, datetime

import pandas as pd

from quantforge.data.reference import (
    normalize_security_master,
    normalize_trade_calendar,
    validate_security_master,
    validate_trade_calendar,
)

INGESTED_AT = datetime(2024, 1, 9, tzinfo=UTC)


def test_trade_calendar_normalization_and_quality() -> None:
    vendor = pd.DataFrame(
        {
            "calendar_date": ["2024-01-01", "2024-01-02"],
            "is_trading_day": ["0", "1"],
        }
    )

    frame = normalize_trade_calendar(vendor, source="baostock", ingested_at=INGESTED_AT)
    report = validate_trade_calendar(frame)

    assert frame["is_trading_day"].tolist() == [False, True]
    assert report.passed


def test_security_master_preserves_listing_lifecycle() -> None:
    vendor = pd.DataFrame(
        {
            "code": ["sh.600000", "sz.000001"],
            "code_name": ["Fixture A", "Fixture B"],
            "ipoDate": ["1999-11-10", "1991-04-03"],
            "outDate": ["", "2025-01-01"],
            "type": ["1", "1"],
            "status": ["1", "0"],
        }
    )

    frame = normalize_security_master(vendor, source="baostock", ingested_at=INGESTED_AT)
    report = validate_security_master(frame)

    assert frame["instrument_id"].tolist() == ["600000.SH", "000001.SZ"]
    assert pd.isna(frame.loc[0, "delist_date"])
    assert report.passed


def test_reference_quality_rejects_duplicates_and_impossible_lifecycle() -> None:
    vendor = pd.DataFrame(
        {
            "code": ["sh.600000", "sh.600000"],
            "code_name": ["Fixture", "Fixture"],
            "ipoDate": ["2024-01-02", "2024-01-02"],
            "outDate": ["2023-01-01", "2023-01-01"],
            "type": ["1", "1"],
            "status": ["0", "0"],
        }
    )
    frame = normalize_security_master(vendor, source="baostock", ingested_at=INGESTED_AT)

    report = validate_security_master(frame)

    assert not report.passed
    assert {issue.check for issue in report.issues} == {
        "duplicate_instrument",
        "invalid_listing_lifecycle",
    }
