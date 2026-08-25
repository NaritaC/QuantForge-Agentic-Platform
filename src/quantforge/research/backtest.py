from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    orders: pd.DataFrame
    fills: pd.DataFrame
    holdings: pd.DataFrame
    nav: pd.DataFrame
    metrics: dict[str, Any]


def _blocked_reason(row: pd.Series | None, side: str, require_price_limits: bool) -> str | None:
    if row is None:
        return "missing_quote"
    if str(row["trade_status"]) != "TRADE":
        return "suspended"
    if pd.isna(row["open"]) or float(row["open"]) <= 0:
        return "invalid_open"
    if pd.isna(row["upper_limit"]) or pd.isna(row["lower_limit"]):
        return "price_limits_missing" if require_price_limits else None
    if side == "BUY" and float(row["open"]) >= float(row["upper_limit"]):
        return "limit_up"
    if side == "SELL" and float(row["open"]) <= float(row["lower_limit"]):
        return "limit_down"
    return None


def _metrics(nav: pd.DataFrame, fills: pd.DataFrame, initial_cash: float) -> dict[str, Any]:
    if nav.empty:
        return {
            "initial_cash": initial_cash,
            "final_equity": initial_cash,
            "total_return": 0.0,
            "annualized_return": None,
            "annualized_volatility": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "turnover": 0.0,
            "trade_count": 0,
        }
    returns = nav["daily_return"].dropna()
    total_return = float(nav.iloc[-1]["equity"] / initial_cash - 1.0)
    years = max((len(nav) - 1) / 252.0, 0.0)
    annualized_return = (1.0 + total_return) ** (1.0 / years) - 1.0 if years > 0 else None
    annualized_volatility = float(returns.std(ddof=0) * math.sqrt(252)) if len(returns) else None
    sharpe = (
        float(returns.mean() / returns.std(ddof=0) * math.sqrt(252))
        if len(returns) > 1 and returns.std(ddof=0) > 0
        else None
    )
    drawdown = nav["equity"] / nav["equity"].cummax() - 1.0
    turnover = (
        float(fills["notional"].abs().sum() / nav["equity"].mean()) if not fills.empty else 0.0
    )
    return {
        "initial_cash": initial_cash,
        "final_equity": float(nav.iloc[-1]["equity"]),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "max_drawdown": float(drawdown.min()),
        "turnover": turnover,
        "trade_count": len(fills),
        "start_date": nav.iloc[0]["trade_date"],
        "end_date": nav.iloc[-1]["trade_date"],
    }


def run_next_open_backtest(
    daily_bars: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    initial_cash: float = 1_000_000.0,
    lot_size: int = 100,
    commission_bps: float = 0.86,
    minimum_commission: float = 5.0,
    stamp_duty_bps: float = 5.0,
    slippage_bps: float = 2.0,
    unfilled_retry_days: int = 5,
    require_price_limits: bool = True,
) -> BacktestResult:
    """Execute close-known targets at next open with explicit A-share constraints."""

    if initial_cash <= 0 or lot_size <= 0 or unfilled_retry_days < 0:
        raise ValueError("Cash and lot size must be positive; retry days cannot be negative")
    bar_required = {
        "trade_date",
        "instrument_id",
        "open",
        "close",
        "trade_status",
        "upper_limit",
        "lower_limit",
    }
    signal_required = {"signal_date", "instrument_id", "target_weight"}
    missing_bars = sorted(bar_required - set(daily_bars.columns))
    missing_signals = sorted(signal_required - set(signals.columns))
    if missing_bars:
        raise ValueError(f"Daily bars missing backtest columns: {', '.join(missing_bars)}")
    if missing_signals:
        raise ValueError(f"Signals missing backtest columns: {', '.join(missing_signals)}")

    bars = daily_bars.copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    bars = bars.sort_values(["trade_date", "instrument_id"], kind="stable")
    signal_frame = signals.copy()
    signal_frame["signal_date"] = pd.to_datetime(signal_frame["signal_date"]).dt.normalize()
    dates = bars["trade_date"].drop_duplicates().sort_values().tolist()
    next_date = {current: following for current, following in zip(dates, dates[1:], strict=False)}
    executions: dict[pd.Timestamp, pd.DataFrame] = {}
    for signal_date, group in signal_frame.groupby("signal_date", sort=True):
        if signal_date in next_date:
            executions[next_date[signal_date]] = group

    quote_lookup = {
        (row.trade_date, row.instrument_id): row for row in bars.itertuples(index=False)
    }
    latest_close: dict[str, float] = {}
    shares: dict[str, int] = {}
    cash = float(initial_cash)
    pending: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    holding_rows: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    order_number = 0
    first_execution = min(executions) if executions else None

    for trade_date in dates:
        day = bars.loc[bars["trade_date"].eq(trade_date)]
        day_quotes = {row.instrument_id: row for row in day.itertuples(index=False)}
        if trade_date in executions:
            targets = executions[trade_date]
            weights = dict(zip(targets["instrument_id"], targets["target_weight"], strict=True))
            open_equity = cash + sum(
                quantity
                * float(
                    getattr(day_quotes.get(instrument), "open", latest_close.get(instrument, 0.0))
                )
                for instrument, quantity in shares.items()
            )
            signal_date = pd.Timestamp(targets.iloc[0]["signal_date"])
            for instrument in sorted(set(shares) | set(weights)):
                quote = day_quotes.get(instrument)
                open_price = (
                    float(quote.open) if quote is not None else latest_close.get(instrument)
                )
                if not open_price:
                    continue
                desired = int((open_equity * weights.get(instrument, 0.0) / open_price) // lot_size)
                desired *= lot_size
                delta = desired - shares.get(instrument, 0)
                if delta:
                    order_number += 1
                    pending.append(
                        {
                            "order_id": f"O{order_number:06d}",
                            "signal_date": signal_date,
                            "scheduled_date": trade_date,
                            "instrument_id": instrument,
                            "side": "BUY" if delta > 0 else "SELL",
                            "requested_quantity": abs(delta),
                            "retry_count": 0,
                        }
                    )

        pending.sort(key=lambda order: 0 if order["side"] == "SELL" else 1)
        remaining: list[dict[str, Any]] = []
        for order in pending:
            quote_tuple = quote_lookup.get((trade_date, order["instrument_id"]))
            quote = pd.Series(quote_tuple._asdict()) if quote_tuple is not None else None
            reason = _blocked_reason(quote, order["side"], require_price_limits)
            if reason:
                will_retry = order["retry_count"] < unfilled_retry_days
                order_rows.append(
                    {
                        **order,
                        "attempt_date": trade_date,
                        "status": "retry_pending" if will_retry else "expired",
                        "reason": reason,
                    }
                )
                if will_retry:
                    remaining.append({**order, "retry_count": order["retry_count"] + 1})
                continue

            open_price = float(quote["open"])
            price = open_price * (
                1.0 + slippage_bps / 10_000
                if order["side"] == "BUY"
                else 1.0 - slippage_bps / 10_000
            )
            quantity = int(order["requested_quantity"])
            if order["side"] == "SELL":
                quantity = min(quantity, shares.get(order["instrument_id"], 0))
            else:
                while quantity > 0:
                    notional = quantity * price
                    commission = max(minimum_commission, notional * commission_bps / 10_000)
                    if notional + commission <= cash:
                        break
                    quantity -= lot_size
            if quantity <= 0:
                order_rows.append(
                    {**order, "attempt_date": trade_date, "status": "rejected", "reason": "cash"}
                )
                continue
            notional = quantity * price
            commission = max(minimum_commission, notional * commission_bps / 10_000)
            stamp_duty = notional * stamp_duty_bps / 10_000 if order["side"] == "SELL" else 0.0
            if order["side"] == "BUY":
                cash -= notional + commission
                shares[order["instrument_id"]] = shares.get(order["instrument_id"], 0) + quantity
            else:
                cash += notional - commission - stamp_duty
                shares[order["instrument_id"]] = shares.get(order["instrument_id"], 0) - quantity
            order_rows.append(
                {**order, "attempt_date": trade_date, "status": "filled", "reason": None}
            )
            fill_rows.append(
                {
                    "order_id": order["order_id"],
                    "signal_date": order["signal_date"],
                    "trade_date": trade_date,
                    "instrument_id": order["instrument_id"],
                    "side": order["side"],
                    "quantity": quantity,
                    "open_price": open_price,
                    "fill_price": price,
                    "notional": notional,
                    "commission": commission,
                    "stamp_duty": stamp_duty,
                    "slippage_bps": slippage_bps,
                }
            )
        pending = remaining

        for row in day.itertuples(index=False):
            if pd.notna(row.close):
                latest_close[row.instrument_id] = float(row.close)
        if first_execution is None or trade_date < first_execution:
            continue
        market_value = sum(
            quantity * latest_close.get(instrument, 0.0)
            for instrument, quantity in shares.items()
            if quantity
        )
        equity = cash + market_value
        for instrument, quantity in sorted(shares.items()):
            if quantity:
                holding_rows.append(
                    {
                        "trade_date": trade_date,
                        "instrument_id": instrument,
                        "quantity": quantity,
                        "close": latest_close.get(instrument),
                        "market_value": quantity * latest_close.get(instrument, 0.0),
                    }
                )
        nav_rows.append(
            {
                "trade_date": trade_date,
                "cash": cash,
                "market_value": market_value,
                "equity": equity,
                "nav": equity / initial_cash,
                "position_count": sum(quantity > 0 for quantity in shares.values()),
            }
        )

    orders = pd.DataFrame(order_rows)
    fills = pd.DataFrame(fill_rows)
    holdings = pd.DataFrame(holding_rows)
    nav = pd.DataFrame(nav_rows)
    if not nav.empty:
        nav["daily_return"] = nav["equity"].pct_change()
    return BacktestResult(orders, fills, holdings, nav, _metrics(nav, fills, initial_cash))
