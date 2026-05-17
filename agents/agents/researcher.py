"""Researcher Agent — Bullish / Bearish debate + Facilitator integration.

Flow (2 rounds, 4 messages):
  Round 1: Bull initial → Bear responds
  Round 2: Bull rebuts  → Bear final
  Facilitator: integrates all 4 messages → ResearchReport
"""

import json

from agents.base import BaseAgent
from agents.models import (
    ChipReport, FundamentalReport, NewsReport,
    ResearchReport, SentimentReport, TechnicalReport,
)
from config import settings
from llm.base import BaseLLMProvider


class Researcher(BaseAgent):
    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._bull_system = self.load_prompt("researcher_bull")
        self._bear_system = self.load_prompt("researcher_bear")
        self._fac_system  = self.load_prompt("researcher_facilitator")

    async def analyze(
        self,
        stock_id: str,
        technical:    TechnicalReport    | None,
        fundamental:  FundamentalReport  | None,
        sentiment:    SentimentReport    | None,
        news:         NewsReport         | None,
        chip:         ChipReport         | None,
    ) -> ResearchReport:
        self._log_call(stock_id)

        reports_text = _format_reports(stock_id, technical, fundamental, sentiment, news, chip)
        rounds = settings.debate_rounds  # default 2

        # ── Debate rounds ────────────────────────────────────────────────────
        bull_msgs: list[str] = []
        bear_msgs: list[str] = []

        for i in range(rounds):
            # Bull speaks (or rebuts)
            if i == 0:
                bull_user = (
                    f"【分析師報告摘要】\n{reports_text}\n\n"
                    "請提出你的做多論點。"
                )
            else:
                bull_user = (
                    f"空方回應：{bear_msgs[-1]}\n\n"
                    "請針對空方質疑提出回應。"
                )
            bull_arg = await self.llm.chat(self._bull_system, bull_user)
            bull_msgs.append(bull_arg)
            self.log.debug("bull round", stock_id=stock_id, round=i + 1)

            # Bear responds
            bear_user = (
                f"【分析師報告摘要】\n{reports_text}\n\n"
                f"多方論點：{bull_arg}\n\n"
                "請提出你的反駁。"
            )
            bear_arg = await self.llm.chat(self._bear_system, bear_user)
            bear_msgs.append(bear_arg)
            self.log.debug("bear round", stock_id=stock_id, round=i + 1)

        # ── Facilitator integrates ───────────────────────────────────────────
        debate_log = "\n\n".join(
            f"【多方 第{i+1}輪】{b}\n【空方 第{i+1}輪】{e}"
            for i, (b, e) in enumerate(zip(bull_msgs, bear_msgs))
        )
        fac_user = (
            f"股票：{stock_id}\n\n"
            f"=== 分析師報告 ===\n{reports_text}\n\n"
            f"=== 辯論紀錄 ===\n{debate_log}\n\n"
            "請整合以上辯論，給出最終研究結論。"
        )
        report = await self.llm.chat_structured(self._fac_system, fac_user, ResearchReport)

        self.log.info(
            "research done",
            stock_id=stock_id,
            view=report.prevailing_view,
            recommendation=report.final_recommendation,
        )
        return report


def _format_reports(
    stock_id: str,
    technical:   TechnicalReport    | None,
    fundamental: FundamentalReport  | None,
    sentiment:   SentimentReport    | None,
    news:        NewsReport         | None,
    chip:        ChipReport         | None,
) -> str:
    parts = [f"股票代號：{stock_id}"]
    if technical:
        parts.append(
            f"【技術面】趨勢={technical.trend} 訊號={technical.signal} "
            f"信心={technical.confidence:.0%}\n{technical.summary}"
        )
    if fundamental:
        parts.append(
            f"【基本面】評級={fundamental.rating} "
            f"信心={fundamental.confidence:.0%}\n{fundamental.summary}"
        )
    if chip:
        parts.append(
            f"【籌碼面】法人={chip.institutional_trend} 融資風險={chip.margin_risk} "
            f"得分={chip.chip_score:+.2f}\n{chip.summary}"
        )
    if sentiment:
        parts.append(
            f"【情緒面】得分={sentiment.sentiment_score:+.2f} 熱度={sentiment.heat_level}\n"
            f"{sentiment.summary}"
        )
    if news:
        parts.append(
            f"【新聞面】總經={news.macro_outlook} 公司={news.company_news_impact}\n"
            f"{news.summary}"
        )
    return "\n\n".join(parts)
