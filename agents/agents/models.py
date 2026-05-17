"""Pydantic output models for all agents.

All agents return one of these models via chat_structured().
The models are serialised to JSONB and stored in agent_reports.
"""

from typing import Literal
from pydantic import BaseModel, Field


class FundamentalReport(BaseModel):
    summary: str = Field(description="100字以內的基本面摘要")
    rating: Literal["強力買進", "買進", "中立", "賣出", "強力賣出"]
    key_metrics: dict = Field(description="EPS、毛利率、殖利率等關鍵指標")
    risks: list[str] = Field(description="主要風險清單（3-5項）")
    opportunities: list[str] = Field(description="主要機會清單（3-5項）")
    confidence: float = Field(ge=0.0, le=1.0, description="分析把握程度")


class TechnicalReport(BaseModel):
    summary: str = Field(description="技術面摘要")
    trend: Literal["強勢上漲", "緩步上漲", "橫盤整理", "緩步下跌", "強勢下跌"]
    signal: Literal["買進", "觀望", "賣出"]
    support_level: float = Field(description="近期支撐價位")
    resistance_level: float = Field(description="近期壓力價位")
    indicators_snapshot: dict = Field(description="關鍵指標數值快照")
    confidence: float = Field(ge=0.0, le=1.0)


class SentimentReport(BaseModel):
    summary: str = Field(description="散戶情緒摘要")
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="-1極悲觀，1極樂觀")
    heat_level: Literal["高", "中", "低"] = Field(description="話題熱度")
    notable_topics: list[str] = Field(description="值得注意的討論主題")
    confidence: float = Field(ge=0.0, le=1.0)


class NewsReport(BaseModel):
    summary: str = Field(description="新聞面摘要")
    macro_outlook: Literal["正面", "中性", "負面"]
    company_news_impact: Literal["正面", "中性", "負面", "無重大消息"]
    key_events: list[str] = Field(description="近期重大事件清單")
    confidence: float = Field(ge=0.0, le=1.0)


class ChipReport(BaseModel):
    summary: str = Field(description="籌碼面摘要")
    institutional_trend: Literal["積極買超", "小幅買超", "中立", "小幅賣超", "積極賣超"]
    margin_risk: Literal["低", "中", "高", "極高"] = Field(description="融資風險等級")
    insider_action: Literal["增持", "持平", "減持"]
    chip_score: float = Field(ge=-1.0, le=1.0, description="籌碼綜合分數")
    confidence: float = Field(ge=0.0, le=1.0)


# Phase 3 models（Researcher、Trader、Risk）
class ResearchReport(BaseModel):
    bull_argument: str
    bear_argument: str
    debate_summary: str
    prevailing_view: Literal["多方佔優", "空方佔優", "勢均力敵"]
    final_recommendation: Literal["積極做多", "保守做多", "觀望", "減碼", "出清"]


class TraderDecision(BaseModel):
    action: Literal["買進", "加碼", "持有", "減碼", "賣出", "不動作"]
    position_size: float = Field(ge=0.0, le=1.0, description="佔總資金比例")
    entry_price_range: tuple[float, float] = Field(description="建議進場價區間")
    stop_loss: float
    take_profit: float
    rationale: str = Field(description="決策理由，100字內")


class RiskDecision(BaseModel):
    approved: bool
    adjusted_action: str
    adjusted_position_size: float = Field(ge=0.0, le=1.0)
    risk_notes: list[str]
    portfolio_exposure: dict
