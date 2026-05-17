from __future__ import annotations

from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Integer,
    Numeric, String, Text, UniqueConstraint, func, select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

log = structlog.get_logger("tools.db")


class Base(DeclarativeBase):
    pass


class StockDaily(Base):
    __tablename__ = "stock_daily"
    id         = Column(Integer, primary_key=True)
    stock_id   = Column(String(10), nullable=False)
    date       = Column(Date, nullable=False)
    open       = Column(Numeric(10, 2))
    high       = Column(Numeric(10, 2))
    low        = Column(Numeric(10, 2))
    close      = Column(Numeric(10, 2))
    volume     = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("stock_id", "date"),)


class PTTPost(Base):
    __tablename__ = "ptt_posts"
    id         = Column(Integer, primary_key=True)
    article_id = Column(String(50), unique=True)
    title      = Column(Text)
    author     = Column(String(50))
    push_count = Column(Integer)
    boo_count  = Column(Integer)
    posted_at  = Column(DateTime)
    crawled_at = Column(DateTime, server_default=func.now())


class NewsArticle(Base):
    __tablename__ = "news_articles"
    id           = Column(Integer, primary_key=True)
    source       = Column(String(50))
    title        = Column(Text)
    summary      = Column(Text)
    url          = Column(Text, unique=True)
    published_at = Column(DateTime)
    crawled_at   = Column(DateTime, server_default=func.now())


class InstitutionalInvestor(Base):
    __tablename__ = "institutional_investors"
    id           = Column(Integer, primary_key=True)
    stock_id     = Column(String(10))
    date         = Column(Date)
    foreign_buy  = Column(BigInteger)
    foreign_sell = Column(BigInteger)
    trust_buy    = Column(BigInteger)
    trust_sell   = Column(BigInteger)
    dealer_buy   = Column(BigInteger)
    dealer_sell  = Column(BigInteger)
    __table_args__ = (UniqueConstraint("stock_id", "date"),)


class AgentReport(Base):
    __tablename__ = "agent_reports"
    id          = Column(Integer, primary_key=True)
    stock_id    = Column(String(10))
    report_date = Column(Date)
    agent_type  = Column(String(50))
    report      = Column(JSONB)
    created_at  = Column(DateTime, server_default=func.now())


class DailyRecommendation(Base):
    __tablename__ = "daily_recommendations"
    id            = Column(Integer, primary_key=True)
    report_date   = Column(Date)
    stock_id      = Column(String(10))
    action        = Column(String(20))
    position_size = Column(Numeric(5, 4))
    stop_loss     = Column(Numeric(10, 2))
    take_profit   = Column(Numeric(10, 2))
    rationale     = Column(Text)
    approved      = Column(Boolean)
    risk_notes    = Column(JSONB)
    created_at    = Column(DateTime, server_default=func.now())


# ── Engine & Session ──────────────────────────────────────────────────────────

_engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# ── Query helpers ─────────────────────────────────────────────────────────────

async def get_stock_prices(
    session: AsyncSession,
    stock_id: str,
    limit: int = 120,
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(StockDaily)
        .where(StockDaily.stock_id == stock_id)
        .order_by(StockDaily.date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "date": r.date.isoformat(),
            "open": float(r.open or 0),
            "high": float(r.high or 0),
            "low": float(r.low or 0),
            "close": float(r.close or 0),
            "volume": r.volume or 0,
        }
        for r in reversed(rows)
    ]


async def get_institutional(
    session: AsyncSession,
    stock_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(InstitutionalInvestor)
        .where(InstitutionalInvestor.stock_id == stock_id)
        .order_by(InstitutionalInvestor.date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "date": r.date.isoformat(),
            "foreign_net": (r.foreign_buy or 0) - (r.foreign_sell or 0),
            "trust_net":   (r.trust_buy or 0)   - (r.trust_sell or 0),
            "dealer_net":  (r.dealer_buy or 0)  - (r.dealer_sell or 0),
        }
        for r in reversed(rows)
    ]


async def get_ptt_posts(
    session: AsyncSession,
    days: int = 3,
) -> list[dict[str, Any]]:
    from sqlalchemy import text
    result = await session.execute(
        select(PTTPost)
        .where(PTTPost.posted_at >= func.now() - text(f"interval '{days} days'"))
        .order_by(PTTPost.posted_at.desc())
        .limit(200)
    )
    rows = result.scalars().all()
    return [
        {
            "title":      r.title,
            "push_count": r.push_count,
            "boo_count":  r.boo_count,
            "posted_at":  r.posted_at.isoformat() if r.posted_at else None,
        }
        for r in rows
    ]


async def get_recent_news(
    session: AsyncSession,
    days: int = 7,
) -> list[dict[str, Any]]:
    from sqlalchemy import text
    result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.published_at >= func.now() - text(f"interval '{days} days'"))
        .order_by(NewsArticle.published_at.desc())
        .limit(100)
    )
    rows = result.scalars().all()
    return [
        {
            "source":       r.source,
            "title":        r.title,
            "summary":      r.summary,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in rows
    ]


async def save_agent_report(
    session: AsyncSession,
    stock_id: str,
    agent_type: str,
    report: dict[str, Any],
    report_date: date | None = None,
) -> None:
    from datetime import date as date_cls
    rec = AgentReport(
        stock_id=stock_id,
        agent_type=agent_type,
        report=report,
        report_date=report_date or date_cls.today(),
    )
    session.add(rec)
    await session.commit()
    log.info("saved agent report", stock_id=stock_id, agent_type=agent_type)
