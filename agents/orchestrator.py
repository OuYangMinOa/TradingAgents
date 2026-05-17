"""Main orchestration flow for Phase 3.

Per-stock pipeline (runs in parallel, semaphore-limited):
  1. Fetch data from DB
  2. Run 5 analysts concurrently
  3. Researcher debate (sequential by design)
  4. Trader decision
  5. Risk review
  6. Save agent_reports to DB

After all stocks:
  7. Generate Markdown report → reports/YYYY-MM-DD.md
  8. Save daily_recommendations to DB
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from agents.chip_analyst import ChipAnalyst
from agents.fundamental_analyst import FundamentalAnalyst
from agents.models import (
    ChipReport, FundamentalReport, NewsReport,
    RiskDecision, SentimentReport, TechnicalReport, TraderDecision,
)
from agents.news_analyst import NewsAnalyst
from agents.researcher import Researcher
from agents.risk_manager import RiskManager
from agents.sentiment_analyst import SentimentAnalyst
from agents.technical_analyst import TechnicalAnalyst
from agents.trader import Trader
from config import STOCK_META, settings
from llm.base import BaseLLMProvider
from tools.db import (
    AsyncSessionLocal, DailyRecommendation,
    get_institutional, get_ptt_posts, get_recent_news,
    get_stock_prices, save_agent_report,
)
from tools.finmind import FinMindClient
from tools.formatter import StockResult, generate_report

log = structlog.get_logger("orchestrator")

# Max stocks processed concurrently (avoids API rate limits)
_CONCURRENCY = 3


class Orchestrator:
    def __init__(self, llm: BaseLLMProvider) -> None:
        self.technical   = TechnicalAnalyst(llm)
        self.fundamental = FundamentalAnalyst(llm)
        self.sentiment   = SentimentAnalyst(llm)
        self.news        = NewsAnalyst(llm)
        self.chip        = ChipAnalyst(llm)
        self.researcher  = Researcher(llm)
        self.trader      = Trader(llm)
        self.risk        = RiskManager(llm)

        # Simple in-memory portfolio (Phase 4 will persist this)
        self._portfolio: dict[str, float] = {}

    async def run(self, run_date: date, stocks: list[str]) -> None:
        log.info("orchestrator start", date=run_date.isoformat(), stocks=len(stocks))

        sem = asyncio.Semaphore(_CONCURRENCY)
        tasks = [self._run_stock_safe(sid, run_date, sem) for sid in stocks]
        results: list[StockResult] = await asyncio.gather(*tasks)

        # Generate Markdown report
        report_path = generate_report(run_date, results)
        log.info("report generated", path=str(report_path))

        # Persist daily recommendations
        async with AsyncSessionLocal() as session:
            await _save_recommendations(session, run_date, results)

        log.info("orchestrator done", date=run_date.isoformat())

    async def _run_stock_safe(
        self, stock_id: str, run_date: date, sem: asyncio.Semaphore
    ) -> StockResult:
        meta = STOCK_META.get(stock_id, {"name": stock_id, "industry": "未分類"})
        result = StockResult(stock_id=stock_id, company_name=meta["name"])

        async with sem:
            try:
                result = await self._run_stock(stock_id, run_date, meta)
            except Exception as exc:
                log.error("stock failed", stock_id=stock_id, error=str(exc))
                result.error = str(exc)

        return result

    async def _run_stock(
        self, stock_id: str, run_date: date, meta: dict
    ) -> StockResult:
        result = StockResult(stock_id=stock_id, company_name=meta["name"])

        async with AsyncSessionLocal() as session:
            # ── 1. Fetch data ─────────────────────────────────────────────
            ohlcv         = await get_stock_prices(session, stock_id, limit=120)
            institutional = await get_institutional(session, stock_id, limit=20)
            ptt_posts     = await get_ptt_posts(session, days=3)
            recent_news   = await get_recent_news(session, days=7)

            if not ohlcv:
                raise ValueError(f"no price data for {stock_id}")

            last_close = ohlcv[-1]["close"]

            # ── 2. Run 5 analysts concurrently ────────────────────────────
            (
                result.technical,
                result.chip,
                result.sentiment,
                result.news,
            ) = await asyncio.gather(
                _safe(self.technical.analyze(stock_id, ohlcv)),
                _safe(self.chip.analyze(stock_id, institutional)),
                _safe(self.sentiment.analyze(stock_id, meta["name"], ptt_posts)),
                _safe(self.news.analyze(stock_id, meta["name"], meta["industry"], recent_news)),
            )

            # Fundamental: fetch from FinMind Python client (quarterly + revenue + dividends)
            result.fundamental = await _safe(_run_fundamental(self.fundamental, stock_id))

            # ── 3. Researcher debate ──────────────────────────────────────
            result.research = await self.researcher.analyze(
                stock_id,
                technical=result.technical,
                fundamental=result.fundamental,
                sentiment=result.sentiment,
                news=result.news,
                chip=result.chip,
            )

            # ── 4. Trader decision ────────────────────────────────────────
            current_pos = self._portfolio.get(stock_id, 0.0)
            result.trader = await self.trader.analyze(
                stock_id,
                research=result.research,
                current_position=current_pos,
                available_capital=1.0 - sum(self._portfolio.values()),
                last_close=last_close,
            )

            # ── 5. Risk review ────────────────────────────────────────────
            result.risk = await self.risk.analyze(
                stock_id,
                trader_decision=result.trader,
                portfolio=self._portfolio,
            )

            # ── 6. Update in-memory portfolio ─────────────────────────────
            if result.risk.approved and result.risk.adjusted_position_size > 0:
                self._portfolio[stock_id] = result.risk.adjusted_position_size

            # ── 7. Save reports to DB ─────────────────────────────────────
            await _persist_reports(session, stock_id, run_date, result)

        return result


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _safe(coro):
    """Swallow per-analyst exceptions so one failure doesn't abort the stock."""
    try:
        return await coro
    except Exception as exc:
        log.warning("analyst failed", error=str(exc))
        return None


async def _run_fundamental(analyst: FundamentalAnalyst, stock_id: str) -> FundamentalReport:
    """Fetch FinMind financial data then run fundamental analyst."""
    async with FinMindClient() as fm:
        data = await fm.fetch_all_fundamental(stock_id)

    # Merge income statement + balance sheet into a single financials list
    financials = data["income_statement"] + data["balance_sheet"]

    if not financials and not data["monthly_revenue"]:
        # API token missing or rate-limited: return low-confidence neutral
        return FundamentalReport(
            summary="FinMind API 無法取得財務資料，請確認 FINMIND_API_TOKEN 設定。",
            rating="中立",
            key_metrics={},
            risks=["財務資料取得失敗"],
            opportunities=[],
            confidence=0.1,
        )

    return await analyst.analyze(
        stock_id=stock_id,
        financials=financials,
        monthly_revenue=data["monthly_revenue"],
        dividends=data["dividends"],
    )


async def _persist_reports(
    session: AsyncSession,
    stock_id: str,
    run_date: date,
    result: StockResult,
) -> None:
    pairs = [
        ("technical",    result.technical),
        ("fundamental",  result.fundamental),
        ("sentiment",    result.sentiment),
        ("news",         result.news),
        ("chip",         result.chip),
        ("researcher",   result.research),
        ("trader",       result.trader),
        ("risk",         result.risk),
    ]
    for agent_type, report in pairs:
        if report is not None:
            await save_agent_report(
                session, stock_id, agent_type,
                report.model_dump(), run_date,
            )


async def _save_recommendations(
    session: AsyncSession,
    run_date: date,
    results: list[StockResult],
) -> None:
    for r in results:
        if r.trader is None or r.risk is None or r.error:
            continue
        rec = DailyRecommendation(
            report_date=run_date,
            stock_id=r.stock_id,
            action=r.risk.adjusted_action,
            position_size=r.risk.adjusted_position_size,
            stop_loss=r.trader.stop_loss,
            take_profit=r.trader.take_profit,
            rationale=r.trader.rationale,
            approved=r.risk.approved,
            risk_notes=r.risk.risk_notes,
        )
        session.add(rec)
    await session.commit()
    log.info("recommendations saved", count=sum(1 for r in results if not r.error))
