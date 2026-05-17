"""Report formatter — produces reports/YYYY-MM-DD.md from analysis results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from agents.models import (
    ChipReport, FundamentalReport, NewsReport,
    ResearchReport, RiskDecision, SentimentReport,
    TechnicalReport, TraderDecision,
)

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


@dataclass
class StockResult:
    stock_id: str
    company_name: str
    technical:   TechnicalReport   | None = None
    fundamental: FundamentalReport | None = None
    sentiment:   SentimentReport   | None = None
    news:        NewsReport        | None = None
    chip:        ChipReport        | None = None
    research:    ResearchReport    | None = None
    trader:      TraderDecision    | None = None
    risk:        RiskDecision      | None = None
    error:       str | None = None


def generate_report(report_date: date, results: list[StockResult]) -> Path:
    """Generate daily Markdown report and return the file path."""
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{report_date.isoformat()}.md"

    lines: list[str] = [
        f"# 台股選股日報 — {report_date.isoformat()}",
        "",
        "## 今日建議操作",
        "",
        "| 股票 | 名稱 | 建議 | 倉位 | 停損 | 停利 | 風控通過 |",
        "|------|------|------|------|------|------|---------|",
    ]

    # Summary table — only include stocks with an approved action
    for r in results:
        if r.risk and r.trader and r.error is None:
            action = r.risk.adjusted_action or (r.trader.action if r.trader else "N/A")
            size   = f"{r.risk.adjusted_position_size:.0%}"
            sl     = f"{r.trader.stop_loss:.0f}"   if r.trader else "N/A"
            tp     = f"{r.trader.take_profit:.0f}" if r.trader else "N/A"
            ok     = "✅" if r.risk.approved else "❌"
            lines.append(f"| {r.stock_id} | {r.company_name} | {action} | {size} | {sl} | {tp} | {ok} |")

    lines += ["", "---", "", "## 各股詳細分析", ""]

    for r in results:
        lines += _stock_section(r)

    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
    return path


def _stars(confidence: float | None) -> str:
    if confidence is None:
        return "⭐ N/A"
    n = round(confidence * 5)
    return "⭐" * n + "☆" * (5 - n)


def _stock_section(r: StockResult) -> list[str]:
    lines = [f"### {r.company_name}（{r.stock_id}）", ""]

    if r.error:
        lines += [f"> ⚠️ 分析失敗：{r.error}", ""]
        return lines

    if r.technical:
        lines.append(
            f"**技術面** {_stars(r.technical.confidence)}：{r.technical.trend} / "
            f"訊號={r.technical.signal} / "
            f"支撐={r.technical.support_level:.0f} 壓力={r.technical.resistance_level:.0f}"
        )
        lines.append(f"> {r.technical.summary}")
        lines.append("")

    if r.fundamental:
        lines.append(
            f"**基本面** {_stars(r.fundamental.confidence)}：評級={r.fundamental.rating}"
        )
        lines.append(f"> {r.fundamental.summary}")
        lines.append("")

    if r.chip:
        lines.append(
            f"**籌碼面** {_stars(r.chip.confidence)}：{r.chip.institutional_trend} / "
            f"融資風險={r.chip.margin_risk} / 得分={r.chip.chip_score:+.2f}"
        )
        lines.append(f"> {r.chip.summary}")
        lines.append("")

    if r.sentiment:
        lines.append(
            f"**情緒面** {_stars(r.sentiment.confidence)}："
            f"情緒={r.sentiment.sentiment_score:+.2f} 熱度={r.sentiment.heat_level}"
        )
        lines.append(f"> {r.sentiment.summary}")
        lines.append("")

    if r.news:
        lines.append(
            f"**新聞面** {_stars(r.news.confidence)}："
            f"總經={r.news.macro_outlook} 公司={r.news.company_news_impact}"
        )
        lines.append(f"> {r.news.summary}")
        lines.append("")

    if r.research:
        lines.append(f"**多方論點**：{r.research.bull_argument}")
        lines.append(f"**空方論點**：{r.research.bear_argument}")
        lines.append(f"**辯論摘要**：{r.research.debate_summary}")
        lines.append(f"**研究結論**：{r.research.prevailing_view} → {r.research.final_recommendation}")
        lines.append("")

    if r.trader and r.risk:
        lines.append(
            f"**最終決策**：{r.risk.adjusted_action} "
            f"倉位={r.risk.adjusted_position_size:.0%} "
            f"停損={r.trader.stop_loss:.0f} 停利={r.trader.take_profit:.0f}"
        )
        if r.trader.rationale:
            lines.append(f"> {r.trader.rationale}")
        if r.risk.risk_notes:
            lines.append("")
            lines.append("**風控備註**：")
            for note in r.risk.risk_notes:
                lines.append(f"- {note}")
        lines.append("")

    lines.append("---")
    lines.append("")
    return lines
