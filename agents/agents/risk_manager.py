"""Risk Management Agent — 積極 / 保守 辯論後由 Fund Manager 裁決。

Hard limits are enforced programmatically after LLM output so they
cannot be overridden by prompt injection or hallucination.
"""

from agents.base import BaseAgent
from agents.models import RiskDecision, TraderDecision
from config import settings
from llm.base import BaseLLMProvider


class RiskManager(BaseAgent):
    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._agg_system  = self.load_prompt("risk_aggressive")
        self._cons_system = self.load_prompt("risk_conservative")
        self._fm_system   = self.load_prompt("risk_fund_manager")

    async def analyze(
        self,
        stock_id: str,
        trader_decision: TraderDecision,
        portfolio: dict,        # {stock_id: position_size} current holdings
        market_hv: float = 0.2, # historical volatility proxy
    ) -> RiskDecision:
        self._log_call(stock_id)

        decision_text = _format_decision(stock_id, trader_decision)
        portfolio_text = _format_portfolio(portfolio)

        context = (
            f"股票代號：{stock_id}\n"
            f"市場波動度（HV）：{market_hv:.0%}\n\n"
            f"【交易員決策】\n{decision_text}\n\n"
            f"【目前投資組合】\n{portfolio_text}\n\n"
        )

        # ── 積極派意見 ────────────────────────────────────────────────────────
        agg_view = await self.llm.chat(
            self._agg_system,
            context + "請給出你的風控意見。",
        )
        self.log.debug("risk aggressive done", stock_id=stock_id)

        # ── 保守派意見 ────────────────────────────────────────────────────────
        cons_view = await self.llm.chat(
            self._cons_system,
            context + f"積極派意見：{agg_view}\n\n請給出你的風控意見。",
        )
        self.log.debug("risk conservative done", stock_id=stock_id)

        # ── Fund Manager 裁決 ─────────────────────────────────────────────────
        fm_user = (
            f"{context}"
            f"積極派意見：{agg_view}\n\n"
            f"保守派意見：{cons_view}\n\n"
            "請做出最終風控裁決。"
        )
        decision = await self.llm.chat_structured(self._fm_system, fm_user, RiskDecision)

        # ── 程式化強制套用硬性規則 ─────────────────────────────────────────────
        decision = _apply_hard_limits(decision, stock_id, portfolio)

        self.log.info(
            "risk done",
            stock_id=stock_id,
            approved=decision.approved,
            size=f"{decision.adjusted_position_size:.0%}",
        )
        return decision


def _apply_hard_limits(
    decision: RiskDecision,
    stock_id: str,
    portfolio: dict,
) -> RiskDecision:
    notes = list(decision.risk_notes)
    size = decision.adjusted_position_size

    # 單一個股上限
    if size > settings.max_position_size:
        notes.append(f"倉位已強制壓縮至 {settings.max_position_size:.0%}（硬性上限）")
        size = settings.max_position_size

    # 最大持股數：10 檔
    active_stocks = {k for k, v in portfolio.items() if v > 0}
    if stock_id not in active_stocks and len(active_stocks) >= 10 and size > 0:
        notes.append("持股數已達 10 檔上限，本次交易不執行")
        size = 0.0

    return decision.model_copy(update={
        "adjusted_position_size": round(size, 4),
        "risk_notes": notes,
    })


def _format_decision(stock_id: str, d: TraderDecision) -> str:
    return (
        f"動作：{d.action}\n"
        f"建議倉位：{d.position_size:.0%}\n"
        f"進場區間：{d.entry_price_low} ~ {d.entry_price_high}\n"
        f"停損：{d.stop_loss}\n"
        f"停利：{d.take_profit}\n"
        f"理由：{d.rationale}"
    )


def _format_portfolio(portfolio: dict) -> str:
    if not portfolio:
        return "目前全部為現金"
    lines = [f"  {sid}: {pct:.0%}" for sid, pct in portfolio.items() if pct > 0]
    total = sum(portfolio.values())
    lines.append(f"  現金：{max(0, 1 - total):.0%}")
    return "\n".join(lines) or "目前全部為現金"
