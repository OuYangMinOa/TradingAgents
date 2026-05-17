"""Backtest runner: loads DB data, builds Backtrader feeds, runs simulation.

Usage (from orchestrator or CLI):
    results = await run_backtest(start="2024-01-01", end="2024-12-31", stocks=["2330"])
    print(results.summary())
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import backtrader as bt
import numpy as np
import pandas as pd
import structlog
from sqlalchemy import select, and_

from backtest.strategy import SignalStrategy
from tools.db import AsyncSessionLocal, DailyRecommendation, StockDaily

log = structlog.get_logger("backtest.runner")

_RISK_FREE_RATE = 0.015   # 年化無風險利率（台灣定存利率約 1.5%）
_TRADING_DAYS   = 252


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    start_date:    date
    end_date:      date
    initial_cash:  float
    final_value:   float
    total_return:  float
    annual_return: float
    sharpe_ratio:  float
    max_drawdown:  float
    win_rate:      float
    profit_factor: float
    total_trades:  int
    won_trades:    int
    lost_trades:   int
    per_stock:     dict[str, dict] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"{'='*50}",
            f"  TradingAgents-TW 回測報告",
            f"{'='*50}",
            f"  期間：{self.start_date} ～ {self.end_date}",
            f"  初始資金：{self.initial_cash:,.0f}",
            f"  最終淨值：{self.final_value:,.0f}",
            f"  總報酬率：{self.total_return:+.2%}",
            f"  年化報酬：{self.annual_return:+.2%}",
            f"  夏普比率：{self.sharpe_ratio:.2f}",
            f"  最大回撤：{self.max_drawdown:.2%}",
            f"  勝率：    {self.win_rate:.2%}  ({self.won_trades}W / {self.lost_trades}L)",
            f"  獲利因子：{self.profit_factor:.2f}",
            f"{'='*50}",
        ]
        return "\n".join(lines)

    def to_markdown(self) -> str:
        return (
            f"## 回測績效摘要\n\n"
            f"| 指標 | 數值 |\n"
            f"|------|------|\n"
            f"| 期間 | {self.start_date} ～ {self.end_date} |\n"
            f"| 初始資金 | {self.initial_cash:,.0f} |\n"
            f"| 最終淨值 | {self.final_value:,.0f} |\n"
            f"| 總報酬率 | {self.total_return:+.2%} |\n"
            f"| 年化報酬 | {self.annual_return:+.2%} |\n"
            f"| 夏普比率 | {self.sharpe_ratio:.2f} |\n"
            f"| 最大回撤 | {self.max_drawdown:.2%} |\n"
            f"| 勝率 | {self.win_rate:.2%} ({self.won_trades}W/{self.lost_trades}L) |\n"
            f"| 獲利因子 | {self.profit_factor:.2f} |\n"
        )


# ── Async DB loaders ───────────────────────────────────────────────────────────

async def _load_prices(
    stocks: list[str], start: date, end: date
) -> dict[str, pd.DataFrame]:
    """Load OHLCV data from DB into per-stock DataFrames."""
    result: dict[str, pd.DataFrame] = {}
    async with AsyncSessionLocal() as session:
        for stock_id in stocks:
            rows = (await session.execute(
                select(StockDaily)
                .where(and_(
                    StockDaily.stock_id == stock_id,
                    StockDaily.date >= start,
                    StockDaily.date <= end,
                ))
                .order_by(StockDaily.date)
            )).scalars().all()

            if not rows:
                log.warning("no price data", stock_id=stock_id)
                continue

            df = pd.DataFrame([{
                "datetime": r.date,
                "open":     float(r.open  or 0),
                "high":     float(r.high  or 0),
                "low":      float(r.low   or 0),
                "close":    float(r.close or 0),
                "volume":   float(r.volume or 0),
            } for r in rows])
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)
            result[stock_id] = df

    return result


async def _load_signals(
    stocks: list[str], start: date, end: date
) -> dict[str, dict[date, dict]]:
    """Load approved signals from daily_recommendations."""
    signals: dict[str, dict[date, dict]] = {}
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(DailyRecommendation)
            .where(and_(
                DailyRecommendation.stock_id.in_(stocks),
                DailyRecommendation.report_date >= start,
                DailyRecommendation.report_date <= end,
                DailyRecommendation.approved == True,  # noqa: E712
            ))
        )).scalars().all()

    for r in rows:
        if r.stock_id not in signals:
            signals[r.stock_id] = {}
        signals[r.stock_id][r.report_date] = {
            "action":        r.action,
            "position_size": float(r.position_size or 0),
            "stop_loss":     float(r.stop_loss or 0) or None,
            "take_profit":   float(r.take_profit or 0) or None,
            "approved":      r.approved,
        }

    log.info("signals loaded", total=sum(len(v) for v in signals.values()))
    return signals


# ── Main runner ────────────────────────────────────────────────────────────────

async def run_backtest(
    start: date,
    end:   date,
    stocks: list[str],
    initial_cash: float = 1_000_000,
) -> BacktestResult:
    """Run backtest and return metrics. This is the main entry point."""
    log.info("backtest start", start=start, end=end, stocks=len(stocks))

    # Async DB queries
    price_data, signal_data = await asyncio.gather(
        _load_prices(stocks, start, end),
        _load_signals(stocks, start, end),
    )

    stocks_with_data = list(price_data.keys())
    if not stocks_with_data:
        raise ValueError("No price data found in DB for the given period. Run Go collector first.")

    # Hand off to synchronous Backtrader
    return _run_bt(stocks_with_data, price_data, signal_data, start, end, initial_cash)


def _run_bt(
    stocks:       list[str],
    price_data:   dict[str, pd.DataFrame],
    signal_data:  dict[str, dict[date, dict]],
    start:        date,
    end:          date,
    initial_cash: float,
) -> BacktestResult:
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.001425)

    # Add data feeds
    for stock_id in stocks:
        df = price_data[stock_id]
        feed = bt.feeds.PandasData(dataname=df, name=stock_id)
        cerebro.adddata(feed)

    # Add strategy
    cerebro.addstrategy(SignalStrategy, signals=signal_data)

    # Analyzers
    cerebro.addanalyzer(bt.analyzers.TimeReturn,    _name="time_return")
    cerebro.addanalyzer(bt.analyzers.DrawDown,      _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio,
                        _name="sharpe",
                        riskfreerate=_RISK_FREE_RATE,
                        annualize=True,
                        factor=_TRADING_DAYS)

    log.info("running cerebro", stocks=stocks)
    result_strategies = cerebro.run()
    strat = result_strategies[0]

    final_value = cerebro.broker.getvalue()
    return _collect_metrics(strat, start, end, initial_cash, final_value)


def _collect_metrics(
    strat,
    start:        date,
    end:          date,
    initial_cash: float,
    final_value:  float,
) -> BacktestResult:
    # Time returns
    time_ret = strat.analyzers.time_return.get_analysis()
    ret_series = pd.Series(time_ret).sort_index().dropna()

    total_return = (final_value - initial_cash) / initial_cash
    n_years = max((end - start).days / 365, 1 / 365)
    annual_return = (1 + total_return) ** (1 / n_years) - 1

    # Sharpe ratio
    sharpe_data = strat.analyzers.sharpe.get_analysis()
    sharpe = float(sharpe_data.get("sharperatio") or 0)

    # Max drawdown
    dd_data = strat.analyzers.drawdown.get_analysis()
    max_drawdown = float(dd_data.get("max", {}).get("drawdown", 0)) / 100

    # Trade stats
    trade_data = strat.analyzers.trades.get_analysis()
    total_trades = int(trade_data.get("total", {}).get("closed", 0))
    won_trades   = int(trade_data.get("won",   {}).get("total",  0))
    lost_trades  = int(trade_data.get("lost",  {}).get("total",  0))
    win_rate     = won_trades / total_trades if total_trades > 0 else 0.0

    gross_profit = float(trade_data.get("won",  {}).get("pnl", {}).get("total", 0))
    gross_loss   = abs(float(trade_data.get("lost", {}).get("pnl", {}).get("total", 0)))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return BacktestResult(
        start_date=start,
        end_date=end,
        initial_cash=initial_cash,
        final_value=final_value,
        total_return=total_return,
        annual_return=annual_return,
        sharpe_ratio=sharpe,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        won_trades=won_trades,
        lost_trades=lost_trades,
    )
