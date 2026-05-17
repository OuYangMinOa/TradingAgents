import json

from agents.base import BaseAgent
from agents.models import FundamentalReport
from llm.base import BaseLLMProvider


class FundamentalAnalyst(BaseAgent):
    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._system = self.load_prompt("fundamental")

    async def analyze(
        self,
        stock_id: str,
        financials: list[dict],      # 最近 4 季財報
        monthly_revenue: list[dict], # 最近 12 個月營收
        dividends: list[dict],       # 近 3 年股利
    ) -> FundamentalReport:
        self._log_call(stock_id)

        user = (
            f"股票代號：{stock_id}\n\n"
            f"【近 4 季財務報表摘要】\n"
            f"{json.dumps(financials, ensure_ascii=False, indent=2)}\n\n"
            f"【近 12 個月月營收】\n"
            f"{json.dumps(monthly_revenue, ensure_ascii=False, indent=2)}\n\n"
            f"【近 3 年股利政策】\n"
            f"{json.dumps(dividends, ensure_ascii=False, indent=2)}\n\n"
            "請根據以上資料給出基本面分析。"
        )

        report = await self.llm.chat_structured(self._system, user, FundamentalReport)
        self.log.info("fundamental done", stock_id=stock_id, rating=report.rating)
        return report
