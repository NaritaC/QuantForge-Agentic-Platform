from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from quantforge.data.adapters.baostock import (
    DAILY_FIELDS,
    BaoStockAdapter,
    BaoStockError,
    to_baostock_code,
)
from quantforge.data.normalize import normalize_daily_bars
from quantforge.data.quality import validate_daily_bars


class FakeResult:
    def __init__(
        self,
        fields: list[str],
        rows: list[list[str]],
        *,
        error_code: str = "0",
        error_msg: str = "success",
    ) -> None:
        self.fields = fields
        self.rows = rows
        self.error_code = error_code
        self.error_msg = error_msg
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBaoStock:
    def __init__(self, *, query_error: bool = False) -> None:
        self.query_error = query_error
        self.login_calls = 0
        self.logout_calls = 0

    def login(self) -> SimpleNamespace:
        self.login_calls += 1
        return SimpleNamespace(error_code="0", error_msg="success")

    def logout(self) -> SimpleNamespace:
        self.logout_calls += 1
        return SimpleNamespace(error_code="0", error_msg="success")

    def query_history_k_data_plus(self, code: str, fields: str, **kwargs: str) -> FakeResult:
        if self.query_error:
            return FakeResult([], [], error_code="1001", error_msg="fixture failure")
        close = "6.60" if code == "sh.600000" else "9.50"
        row = [
            "2024-01-02",
            code,
            close,
            close,
            close,
            close,
            close,
            "100",
            "660",
            "3",
            "0.1",
            "1",
            "0.0",
            "0",
        ]
        assert fields == ",".join(DAILY_FIELDS)
        assert kwargs["adjustflag"] == "3"
        return FakeResult(list(DAILY_FIELDS), [row])

    def query_trade_dates(self, **kwargs: str) -> FakeResult:
        return FakeResult(["calendar_date", "is_trading_day"], [["2024-01-02", "1"]])

    def query_stock_basic(self, code: str) -> FakeResult:
        return FakeResult(
            ["code", "code_name", "ipoDate", "outDate", "type", "status"],
            [[code, "Fixture Corp", "2000-01-01", "", "1", "1"]],
        )


def test_to_baostock_code_uses_vendor_market_prefix() -> None:
    assert to_baostock_code("600000.SH") == "sh.600000"
    assert to_baostock_code("000001") == "sz.000001"


def test_adapter_returns_vendor_payload_and_canonical_input_frame() -> None:
    sdk = FakeBaoStock()
    adapter = BaoStockAdapter(
        symbols=["600000.SH", "000001.SZ"],
        start_date="2024-01-02",
        end_date="2024-01-02",
        sdk=sdk,
    )

    batch = adapter.fetch_daily_bars()

    assert sdk.login_calls == 1
    assert sdk.logout_calls == 1
    assert batch.source == "baostock"
    assert batch.frame["symbol"].tolist() == ["sh.600000", "sz.000001"]
    assert batch.frame[["upper_limit", "lower_limit"]].isna().all().all()
    assert b"date,code,open" in (batch.raw_payload or b"")

    normalized = normalize_daily_bars(
        batch.frame,
        source=batch.source,
        ingested_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    report = validate_daily_bars(normalized)
    assert report.passed
    assert {issue.check for issue in report.issues} == {"missing_price_limits"}


def test_adapter_always_logs_out_after_query_failure() -> None:
    sdk = FakeBaoStock(query_error=True)
    adapter = BaoStockAdapter(
        symbols=["600000.SH"],
        start_date="2024-01-02",
        end_date="2024-01-02",
        sdk=sdk,
    )

    with pytest.raises(BaoStockError, match="1001"):
        adapter.fetch_daily_bars()

    assert sdk.logout_calls == 1


def test_calendar_and_security_master_share_the_same_adapter_contract() -> None:
    adapter = BaoStockAdapter(
        symbols=["600000.SH"],
        start_date="2024-01-02",
        end_date="2024-01-02",
        sdk=FakeBaoStock(),
    )

    calendar = adapter.fetch_trade_calendar()
    master = adapter.fetch_security_master()

    pd.testing.assert_frame_equal(
        calendar.frame,
        pd.DataFrame([["2024-01-02", "1"]], columns=["calendar_date", "is_trading_day"]),
    )
    assert master.frame.loc[0, "ipoDate"] == "2000-01-01"
