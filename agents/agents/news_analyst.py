import json

from agents.base import BaseAgent
from agents.models import NewsReport
from llm.base import BaseLLMProvider


class NewsAnalyst(BaseAgent):
    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._system = self.load_prompt("news")

    async def analyze(
        self,
        stock_id: str,
        company_name: str,
        industry: str,
        news: list[dict],  # 近 7 日新聞
    ) -> NewsReport:
        self._log_call(stock_id)

        user = (
            f"股票代號：{stock_id}（{company_name}）\n"
            f"產業別：{industry}\n\n"
            f"【近 7 日財經新聞】\n"
            f"{json.dumps(news, ensure_ascii=False, indent=2)}\n\n"
            "請根據以上新聞，分析對該公司及總體環境的影響。"
        )

        report = await self.llm.chat_structured(self._system, user, NewsReport)
        self.log.info("news done", stock_id=stock_id, macro=report.macro_outlook)
        return report
