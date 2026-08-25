from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

import pandas as pd

from quantforge.data.adapters.base import AdapterBatch


class SyntheticResearchAdapter:
    """Deterministic vendor-shaped data for end-to-end functional demonstrations only."""

    name = "synthetic_fixture"
    version = "1.0.0"

    def __init__(
        self,
        *,
        start_date: str = "2022-01-03",
        periods: int = 520,
        instrument_count: int = 8,
        **_: Any,
    ) -> None:
        if periods < 300:
            raise ValueError("Synthetic research fixture requires at least 300 business days")
        if instrument_count < 3:
            raise ValueError("Synthetic research fixture requires at least three instruments")
        self.start_date = start_date
        self.periods = periods
        self.instrument_count = instrument_count
        self.dates = pd.bdate_range(start_date, periods=periods)
        self.symbols = tuple(f"{600001 + index:06d}.SH" for index in range(instrument_count))

    @staticmethod
    def _raw_csv(frame: pd.DataFrame) -> bytes:
        return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")

    def _daily_frame(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        closes = {symbol: 9.0 + index * 2.5 for index, symbol in enumerate(self.symbols)}
        for day_index, trade_date in enumerate(self.dates):
            for instrument_index, symbol in enumerate(self.symbols):
                previous = closes[symbol]
                cyclical = math.sin((day_index + instrument_index * 7) / 19.0) * 0.004
                drift = (instrument_index - (self.instrument_count - 1) / 2) * 0.00008
                close = max(1.0, previous * (1.0 + drift + cyclical))
                open_price = previous * (
                    1.0 + math.cos((day_index + instrument_index * 3) / 13.0) * 0.0015
                )
                high = max(open_price, close) * 1.008
                low = min(open_price, close) * 0.992
                suspended = instrument_index == 0 and day_index in {330, 331}
                if suspended:
                    open_price = high = low = close = previous
                    volume = 0.0
                else:
                    volume = float(1_000_000 + instrument_index * 180_000 + day_index * 1_000)
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": trade_date.date(),
                        "open": round(open_price, 4),
                        "high": round(high, 4),
                        "low": round(low, 4),
                        "close": round(close, 4),
                        "preclose": round(previous, 4),
                        "volume": volume,
                        "amount": round(volume * close, 2),
                        "tradestatus": "0" if suspended else "1",
                        "is_st": "1" if instrument_index == 1 and day_index >= 440 else "0",
                        "upper_limit": round(previous * 1.10, 4),
                        "lower_limit": round(previous * 0.90, 4),
                    }
                )
                closes[symbol] = close
        return pd.DataFrame(rows)

    def fetch_daily_bars(self) -> AdapterBatch:
        frame = self._daily_frame()
        request = {
            "kind": "deterministic_synthetic_fixture",
            "start_date": self.start_date,
            "periods": self.periods,
            "instrument_count": self.instrument_count,
            "calendar": "weekday_only_not_exchange_calendar",
            "research_evidence": False,
        }
        return AdapterBatch(
            dataset="daily_bars",
            source=self.name,
            adapter_version=self.version,
            request=request,
            frame=frame,
            raw_payload=self._raw_csv(frame),
            source_filename="synthetic_research_daily_bars.csv",
        )

    def fetch_trade_calendar(self) -> AdapterBatch:
        frame = pd.DataFrame({"calendar_date": self.dates.date, "is_trading_day": "1"})
        return AdapterBatch(
            dataset="trade_calendar",
            source=self.name,
            adapter_version=self.version,
            request={"start_date": self.start_date, "periods": self.periods},
            frame=frame,
            raw_payload=self._raw_csv(frame),
            source_filename="synthetic_trade_calendar.csv",
        )

    def fetch_security_master(self) -> AdapterBatch:
        list_date = (self.dates[0].date() - timedelta(days=730)).isoformat()
        frame = pd.DataFrame(
            {
                "code": self.symbols,
                "code_name": [f"Synthetic {index + 1}" for index in range(self.instrument_count)],
                "ipoDate": list_date,
                "outDate": "",
                "type": "1",
                "status": "1",
            }
        )
        return AdapterBatch(
            dataset="security_master",
            source=self.name,
            adapter_version=self.version,
            request={"symbols": list(self.symbols), "research_evidence": False},
            frame=frame,
            raw_payload=self._raw_csv(frame),
            source_filename="synthetic_security_master.csv",
        )
