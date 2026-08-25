from __future__ import annotations

import contextlib
import io
import socket
from types import ModuleType
from typing import Any

import pandas as pd

from quantforge.data.adapters.base import AdapterBatch
from quantforge.data.normalize import normalize_instrument_id

DAILY_FIELDS = (
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "adjustflag",
    "turn",
    "tradestatus",
    "pctChg",
    "isST",
)


class BaoStockError(RuntimeError):
    """Raised when the SDK reports a login, query, or logout failure."""


class _EOFGuardSocket:
    """Prevent the upstream SDK from looping forever after a closed connection."""

    def __init__(self, raw_socket: socket.socket, timeout_seconds: float) -> None:
        self.raw_socket = raw_socket
        self.raw_socket.settimeout(timeout_seconds)

    def send(self, data: bytes) -> int:
        return self.raw_socket.send(data)

    def recv(self, size: int) -> bytes:
        payload = self.raw_socket.recv(size)
        if payload == b"":
            raise ConnectionError("BaoStock server closed the socket before the message completed")
        return payload

    def close(self) -> None:
        self.raw_socket.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw_socket, name)


def to_baostock_code(instrument_id: str) -> str:
    canonical = normalize_instrument_id(instrument_id)
    code, market = canonical.split(".", maxsplit=1)
    return f"{market.lower()}.{code}"


def _load_sdk() -> ModuleType:
    try:
        import baostock as sdk
    except ImportError as error:
        raise BaoStockError(
            "BaoStock adapter is not installed. Run: python -m pip install -e '.[baostock]'"
        ) from error
    return sdk


def _check_result(result: Any, operation: str) -> None:
    if result is None:
        raise BaoStockError(f"BaoStock {operation} returned no result")
    if str(result.error_code) != "0":
        raise BaoStockError(
            f"BaoStock {operation} failed with code {result.error_code}: {result.error_msg}"
        )


def _result_to_frame(result: Any, operation: str) -> pd.DataFrame:
    _check_result(result, operation)
    rows: list[list[str]] = []
    while result.next():
        rows.append(result.get_row_data())
    _check_result(result, operation)
    return pd.DataFrame(rows, columns=result.fields)


class BaoStockSession:
    """One authenticated SDK session with deterministic cleanup and quiet output."""

    def __init__(
        self,
        sdk: ModuleType | Any | None = None,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.sdk = sdk or _load_sdk()
        self.timeout_seconds = timeout_seconds
        self.connected = False

    def _is_real_sdk(self) -> bool:
        return getattr(self.sdk, "__name__", "") == "baostock"

    def _harden_real_socket(self) -> None:
        if not self._is_real_sdk():
            return
        from baostock.common import context

        raw_socket = getattr(context, "default_socket", None)
        if raw_socket is None:
            raise BaoStockError("BaoStock login succeeded without creating a socket")
        if not isinstance(raw_socket, _EOFGuardSocket):
            context.default_socket = _EOFGuardSocket(raw_socket, self.timeout_seconds)

    @staticmethod
    def _quiet_call(function: Any, *args: Any, **kwargs: Any) -> Any:
        with contextlib.redirect_stdout(io.StringIO()):
            return function(*args, **kwargs)

    def __enter__(self) -> BaoStockSession:
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.timeout_seconds)
        try:
            result = self._quiet_call(self.sdk.login)
        finally:
            socket.setdefaulttimeout(previous_timeout)
        _check_result(result, "login")
        self._harden_real_socket()
        self.connected = True
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.connected:
            result = self._quiet_call(self.sdk.logout)
            self.connected = False
            if exc is None:
                _check_result(result, "logout")

    def query_daily_bars(
        self,
        code: str,
        *,
        start_date: str,
        end_date: str,
        adjustflag: str,
    ) -> pd.DataFrame:
        try:
            result = self._quiet_call(
                self.sdk.query_history_k_data_plus,
                code,
                ",".join(DAILY_FIELDS),
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=adjustflag,
            )
            return self._quiet_call(_result_to_frame, result, f"daily-bars query for {code}")
        except (TimeoutError, ConnectionError, OSError) as error:
            raise BaoStockError(f"BaoStock daily-bars query timed out for {code}") from error

    def query_trade_calendar(self, *, start_date: str, end_date: str) -> pd.DataFrame:
        result = self._quiet_call(
            self.sdk.query_trade_dates, start_date=start_date, end_date=end_date
        )
        return self._quiet_call(_result_to_frame, result, "trade-calendar query")

    def query_security_basic(self, code: str) -> pd.DataFrame:
        result = self._quiet_call(self.sdk.query_stock_basic, code=code)
        return self._quiet_call(_result_to_frame, result, f"security-basic query for {code}")

    def query_market_snapshot(self, *, day: str) -> pd.DataFrame:
        result = self._quiet_call(self.sdk.query_all_stock, day=day)
        return self._quiet_call(_result_to_frame, result, f"market-snapshot query for {day}")


def is_a_share_code(code: object) -> bool:
    raw = str(code).strip().lower()
    prefixes = (
        "sh.600",
        "sh.601",
        "sh.603",
        "sh.605",
        "sh.688",
        "sh.689",
        "sz.000",
        "sz.001",
        "sz.002",
        "sz.003",
        "sz.300",
        "sz.301",
        "bj.4",
        "bj.8",
        "bj.9",
    )
    return raw.startswith(prefixes) and len(raw.split(".")[-1]) == 6


class BaoStockAdapter:
    """Vendor adapter that preserves unadjusted observations before normalization."""

    name = "baostock"
    version = "1.0.0"

    def __init__(
        self,
        *,
        symbols: list[str] | tuple[str, ...],
        start_date: str,
        end_date: str,
        adjustflag: str = "3",
        timeout_seconds: float = 30.0,
        sdk: ModuleType | Any | None = None,
    ) -> None:
        if not symbols:
            raise ValueError("BaoStock symbols must not be empty")
        if adjustflag != "3":
            raise ValueError(
                "Canonical Raw daily bars must be unadjusted (BaoStock adjustflag='3'). "
                "Adjustment factors belong in a separate derived dataset."
            )
        self.symbols = tuple(normalize_instrument_id(symbol) for symbol in symbols)
        self.start_date = start_date
        self.end_date = end_date
        self.adjustflag = adjustflag
        self.timeout_seconds = timeout_seconds
        self.sdk = sdk

    @staticmethod
    def _raw_csv(frame: pd.DataFrame) -> bytes:
        return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")

    def fetch_daily_bars(self) -> AdapterBatch:
        frames: list[pd.DataFrame] = []
        with BaoStockSession(self.sdk, timeout_seconds=self.timeout_seconds) as session:
            for symbol in self.symbols:
                frame = session.query_daily_bars(
                    to_baostock_code(symbol),
                    start_date=self.start_date,
                    end_date=self.end_date,
                    adjustflag=self.adjustflag,
                )
                frames.append(frame)
        raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DAILY_FIELDS)
        if raw.empty:
            raise BaoStockError(
                f"BaoStock returned no daily bars for {self.start_date} to {self.end_date}"
            )

        vendor = raw.rename(
            columns={"date": "trade_date", "code": "symbol", "isST": "is_st"}
        ).copy()
        vendor["upper_limit"] = pd.NA
        vendor["lower_limit"] = pd.NA
        request = {
            "symbols": list(self.symbols),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "frequency": "d",
            "adjustflag": self.adjustflag,
            "fields": list(DAILY_FIELDS),
        }
        return AdapterBatch(
            dataset="daily_bars",
            source=self.name,
            adapter_version=self.version,
            request=request,
            frame=vendor,
            raw_payload=self._raw_csv(raw),
            raw_suffix=".csv",
            source_filename="baostock_daily_bars.csv",
        )

    def fetch_trade_calendar(self) -> AdapterBatch:
        with BaoStockSession(self.sdk, timeout_seconds=self.timeout_seconds) as session:
            frame = session.query_trade_calendar(start_date=self.start_date, end_date=self.end_date)
        return AdapterBatch(
            dataset="trade_calendar",
            source=self.name,
            adapter_version=self.version,
            request={"start_date": self.start_date, "end_date": self.end_date},
            frame=frame,
            raw_payload=self._raw_csv(frame),
            source_filename="baostock_trade_calendar.csv",
        )

    def fetch_security_master(self) -> AdapterBatch:
        frames: list[pd.DataFrame] = []
        with BaoStockSession(self.sdk, timeout_seconds=self.timeout_seconds) as session:
            for symbol in self.symbols:
                frames.append(session.query_security_basic(to_baostock_code(symbol)))
        frame = pd.concat(frames, ignore_index=True)
        return AdapterBatch(
            dataset="security_master",
            source=self.name,
            adapter_version=self.version,
            request={"symbols": list(self.symbols)},
            frame=frame,
            raw_payload=self._raw_csv(frame),
            source_filename="baostock_security_master.csv",
        )

    def fetch_market_snapshot(self, as_of_date: str) -> AdapterBatch:
        with BaoStockSession(self.sdk, timeout_seconds=self.timeout_seconds) as session:
            raw = session.query_market_snapshot(day=as_of_date)
        a_shares = raw.loc[raw["code"].map(is_a_share_code)].copy()
        a_shares["instrument_id"] = a_shares["code"].map(normalize_instrument_id)
        a_shares["as_of_date"] = pd.to_datetime(as_of_date).date()
        return AdapterBatch(
            dataset="market_snapshot",
            source=self.name,
            adapter_version=self.version,
            request={
                "as_of_date": as_of_date,
                "security_scope": "A-share code patterns",
                "raw_security_count": len(raw),
                "a_share_count": len(a_shares),
            },
            frame=a_shares,
            raw_payload=self._raw_csv(raw),
            source_filename=f"baostock_market_snapshot_{as_of_date}.csv",
        )
