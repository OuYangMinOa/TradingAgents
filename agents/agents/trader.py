import json

from agents.base import BaseAgent
from agents.models import ResearchReport, TraderDecision
from llm.base import BaseLLMProvider


class Trader(BaseAgent):
    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._system = self.load_prompt("trader")

    async def analyze(
        self,
        stock_id: str,
        research: ResearchReport,
        current_position: float = 0.0,   # 目前持倉比例 0~1
        available_capital: float = 1.0,  # 可用資金比例 0~1
        last_close: float = 0.0,
    ) -> TraderDecision:
        self._log_call(stock_id)

        user = (
            f"股票代號：{stock_id}\n"
            f"最新收盤價：{last_close}\n"
            f"目前持倉比例：{current_position:.0%}\n"
            f"可用資金比例：{available_capital:.0%}\n\n"
            f"【研究結論】\n"
            f"辯論觀點：{research.prevailing_view}\n"
            f"最終建議：{research.final_recommendation}\n\n"
            f"多方論點：{research.bull_argument}\n\n"
            f"空方論點：{research.bear_argument}\n\n"
            f"辯論摘要：{research.debate_summary}\n\n"
            "請根據以上研究結論，做出交易決策。"
        )

        decision = await self.llm.chat_structured(self._system, user, TraderDecision)
        self.log.info(
            "trader done",
            stock_id=stock_id,
            action=decision.action,
            size=f"{decision.position_size:.0%}",
        )
        return decision
