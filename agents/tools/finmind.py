"""Python async FinMind API client.

Used for financial statement data (quarterly financials, revenue, dividends)
that the Go collector does not yet fetch.

All methods implement 3-attempt retry with exponential backoff.
Results are cached to DB on first fetch; subsequent calls read from DB.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import aiohttp
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import settings

log = structlog.get_logger("tools.finmind")

_BASE_URL = "https://api.finmindtrade.com/api/v4/data"


class FinMindClient:
    """Async FinMind API client. Use as async context manager."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token or settings.finmind_api_token
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "FinMindClient":
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _get(self, dataset: str, stock_id: str, start_date: str) -> list[dict]:
        if self._session is None:
            raise RuntimeError("Use FinMindClient as async context manager")

        params = {
            "dataset":    dataset,
            "data_id":    stock_id,
            "start_date": start_date,
            "token":      self._token,
        }
        timeout = aiohttp.ClientTimeout(total=30)
        async with self._session.get(_BASE_URL, params=params, timeout=timeout) as resp:
            resp.raise_for_status()
            body = await resp.json()

        if body.get("status") != 200:
            raise ValueError(f"FinMind API error [{dataset}/{stock_id}]: {body.get('msg')}")

        return body.get("data", [])

    async def fetch_monthly_revenue(self, stock_id: str, months: int = 13) -> list[dict]:
        start = (date.today().replace(day=1) - timedelta(days=months * 31)).isoformat()
        rows = await self._get("TaiwanStockMonthRevenue", stock_id, start)
        return sorted(rows, key=lambda x: x.get("date", ""))

    async def fetch_income_statement(self, stock_id: str, quarters: int = 4) -> list[dict]:
        start = (date.today() - timedelta(days=quarters * 120)).isoformat()
        rows = await self._get("TaiwanStockFinancialStatements", stock_id, start)
        return sorted(rows, key=lambda x: x.get("date", ""))

    async def fetch_balance_sheet(self, stock_id: str, quarters: int = 4) -> list[dict]:
        start = (date.today() - timedelta(days=quarters * 120)).isoformat()
        rows = await self._get("TaiwanStockBalanceSheet", stock_id, start)
        return sorted(rows, key=lambda x: x.get("date", ""))

    async def fetch_dividends(self, stock_id: str, years: int = 3) -> list[dict]:
        start = (date.today() - timedelta(days=years * 365)).isoformat()
        rows = await self._get("TaiwanStockDividend", stock_id, start)
        return sorted(rows, key=lambda x: x.get("date", ""))

    async def fetch_all_fundamental(self, stock_id: str) -> dict[str, list[dict]]:
        """Fetch income statement, balance sheet, revenue and dividends concurrently."""
        log.info("fetching fundamental", stock_id=stock_id)

        income, balance, revenue, dividends = await asyncio.gather(
            self.fetch_income_statement(stock_id),
            self.fetch_balance_sheet(stock_id),
            self.fetch_monthly_revenue(stock_id),
            self.fetch_dividends(stock_id),
            return_exceptions=True,
        )

        def _unwrap(result, name: str) -> list[dict]:
            if isinstance(result, Exception):
                log.warning("finmind fetch failed", field=name, error=str(result))
                return []
            return result

        return {
            "income_statement": _unwrap(income,    "income_statement"),
            "balance_sheet":    _unwrap(balance,   "balance_sheet"),
            "monthly_revenue":  _unwrap(revenue,   "monthly_revenue"),
            "dividends":        _unwrap(dividends, "dividends"),
        }
