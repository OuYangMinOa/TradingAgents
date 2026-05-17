#!/usr/bin/env python
"""Backtest CLI.

Run from project root:
    python scripts/backtest.py --start 2024-01-01 --end 2024-12-31
    python scripts/backtest.py --start 2024-06-01 --end 2024-12-31 --stocks 2330,2454
    python scripts/backtest.py --start 2024-01-01 --end 2024-12-31 --cash 5000000
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Add agents/ to sys.path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from backtest.runner import run_backtest
from config import WATCHLIST


def parse_args() -> argparse.Namespace:
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    parser = argparse.ArgumentParser(
        description="TradingAgents-TW Backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--start", default=one_year_ago.isoformat(),
        help=f"Start date YYYY-MM-DD (default: {one_year_ago})"
    )
    parser.add_argument(
        "--end", default=today.isoformat(),
        help=f"End date YYYY-MM-DD (default: {today})"
    )
    parser.add_argument(
        "--stocks", default="",
        help="Comma-separated stock IDs (default: all watchlist)"
    )
    parser.add_argument(
        "--cash", type=float, default=1_000_000,
        help="Initial capital in TWD (default: 1,000,000)"
    )
    parser.add_argument(
        "--output", default="",
        help="Output Markdown file (default: reports/backtest_<start>_<end>.md)"
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    try:
        start = date.fromisoformat(args.start)
        end   = date.fromisoformat(args.end)
    except ValueError as e:
        print(f"Error: invalid date format — {e}")
        sys.exit(1)

    if start >= end:
        print("Error: --start must be before --end")
        sys.exit(1)

    stocks = [s.strip() for s in args.stocks.split(",") if s.strip()] or WATCHLIST
    print(f"Backtest: {start} → {end}  |  {len(stocks)} stocks  |  NT${args.cash:,.0f}")
    print(f"Stocks: {', '.join(stocks)}")
    print()

    try:
        result = await run_backtest(
            start=start, end=end, stocks=stocks, initial_cash=args.cash
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(result.summary())

    # Save Markdown report
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    output_path = (
        Path(args.output)
        if args.output
        else reports_dir / f"backtest_{start}_{end}.md"
    )

    md_content = (
        f"# TradingAgents-TW 回測報告\n\n"
        f"**生成時間**：{date.today()}\n\n"
        f"{result.to_markdown()}\n\n"
        f"## 參數\n\n"
        f"- 回測期間：{start} ～ {end}\n"
        f"- 初始資金：NT$ {args.cash:,.0f}\n"
        f"- 分析標的：{', '.join(stocks)}\n"
    )
    output_path.write_text(md_content, encoding="utf-8")
    print(f"\nReport saved → {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
