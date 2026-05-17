import json

from agents.base import BaseAgent
from agents.models import SentimentReport
from llm.base import BaseLLMProvider


class SentimentAnalyst(BaseAgent):
    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._system = self.load_prompt("sentiment")

    async def analyze(
        self,
        stock_id: str,
        company_name: str,
        ptt_posts: list[dict],  # 近 3 日 PTT 文章
    ) -> SentimentReport:
        self._log_call(stock_id)

        # Filter posts mentioning the stock ID or company name
        relevant = [
            p for p in ptt_posts
            if stock_id in (p.get("title") or "")
            or company_name in (p.get("title") or "")
        ]

        user = (
            f"股票代號：{stock_id}（{company_name}）\n"
            f"PTT Stock 板近 3 日總文章數：{len(ptt_posts)}\n"
            f"其中提及該股的文章數：{len(relevant)}\n\n"
            f"【相關文章列表】\n"
            f"{json.dumps(relevant[:50], ensure_ascii=False, indent=2)}\n\n"
            "請根據以上資料分析市場情緒。"
        )

        report = await self.llm.chat_structured(self._system, user, SentimentReport)
        self.log.info("sentiment done", stock_id=stock_id, score=report.sentiment_score)
        return report
