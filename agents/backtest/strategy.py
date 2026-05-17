"""Backtrader strategy that replays signals from daily_recommendations.

Signal format (per stock per date):
    {
        "action":        "買進" | "加碼" | "持有" | "減碼" | "賣出" | "不動作",
        "position_size": 0.15,   # fraction of portfolio
        "stop_loss":     850.0,
        "take_profit":   1000.0,
        "approved":      True,
    }
"""

from __future__ import annotations

from datetime import date

import backtrader as bt

# 台股最小交易單位（1張 = 1000股）
_MIN_LOT = 1000


class SignalStrategy(bt.Strategy):
    params = (
        ("signals", {}),    # {stock_id: {date: signal_dict}}
        ("commission", 0.001425),  # 台股手續費 0.1425%（買賣雙向）
        ("tax", 0.003),            # 台股證交稅 0.3%（僅賣方）
    )

    def __init__(self) -> None:
        # Track open stop-loss orders so we can cancel them on close
        self._stop_orders: dict[str, bt.Order] = {}
        self._tp_orders:   dict[str, bt.Order] = {}

    def log(self, msg: str, dt: date | None = None) -> None:
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt}  {msg}")

    def notify_order(self, order: bt.Order) -> None:
        if order.status in (order.Submitted, order.Accepted):
            return
        data_name = order.data._name
        if order.status == order.Completed:
            side = "買入" if order.isbuy() else "賣出"
            self.log(f"{data_name} {side} {order.executed.size}股 @ {order.executed.price:.2f}")
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            self.log(f"{data_name} 訂單失敗 status={order.status}")

    def next(self) -> None:
        portfolio_value = self.broker.getvalue()
        today = self.datas[0].datetime.date(0)

        for data in self.datas:
            stock_id = data._name
            pos = self.getposition(data)

            stock_signals = self.p.signals.get(stock_id, {})
            signal = stock_signals.get(today)

            # ── Stop-loss check (price-based, independent of date signals) ──
            if pos.size > 0 and stock_id in self._stop_orders:
                if data.close[0] <= self._stop_orders[stock_id]:
                    self._close_position(data, stock_id, reason="stop-loss hit")
                    continue

            if signal is None or not signal.get("approved", True):
                continue

            action = signal.get("action", "不動作")

            # ── Execute signal ───────────────────────────────────────────────
            if action in ("買進", "加碼") and pos.size == 0:
                target_pct = signal.get("position_size", 0.10)
                shares = _calc_shares(portfolio_value, target_pct, data.close[0])
                if shares > 0 and self.broker.getcash() >= shares * data.close[0]:
                    self.buy(data=data, size=shares)
                    # Register stop-loss level for next-bar checks
                    sl = signal.get("stop_loss")
                    if sl:
                        self._stop_orders[stock_id] = sl
                    tp = signal.get("take_profit")
                    if tp:
                        self._tp_orders[stock_id] = tp

            elif action in ("賣出", "出清") and pos.size > 0:
                self._close_position(data, stock_id, reason=action)

            elif action == "減碼" and pos.size > 0:
                reduce = pos.size // 2
                if reduce >= _MIN_LOT:
                    self.sell(data=data, size=reduce)

            # ── Take-profit check ────────────────────────────────────────────
            if pos.size > 0 and stock_id in self._tp_orders:
                if data.close[0] >= self._tp_orders[stock_id]:
                    self._close_position(data, stock_id, reason="take-profit hit")

    def _close_position(self, data, stock_id: str, reason: str = "") -> None:
        pos = self.getposition(data)
        if pos.size > 0:
            self.sell(data=data, size=pos.size)
            self.log(f"{stock_id} 平倉 ({reason})")
        self._stop_orders.pop(stock_id, None)
        self._tp_orders.pop(stock_id, None)


def _calc_shares(portfolio_value: float, target_pct: float, price: float) -> int:
    """Calculate share count rounded down to nearest lot (1000 shares)."""
    if price <= 0:
        return 0
    target_value = portfolio_value * target_pct
    raw = int(target_value / price)
    return (raw // _MIN_LOT) * _MIN_LOT
