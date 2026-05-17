import json

from agents.base import BaseAgent
from agents.models import ChipReport
from llm.base import BaseLLMProvider


class ChipAnalyst(BaseAgent):
    """籌碼分析師 — 台股特有，分析三大法人、融資融券、董監持股。

    margin_trading 與 insider_holdings 若無資料傳入空 list，
    Agent 會自動降低 confidence 並在 summary 說明。
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._system = self.load_prompt("chip")

    async def analyze(
        self,
        stock_id: str,
        institutional: list[dict],        # 近 20 日三大法人買賣超（from DB）
        margin_trading: list[dict] = (),  # 近 20 日融資融券（可為空）
        insider_holdings: list[dict] = (), # 近一季董監持股變化（可為空）
    ) -> ChipReport:
        self._log_call(stock_id)

        # Compute net buy/sell totals for quick context
        totals = _summarise_institutional(institutional)

        user = (
            f"股票代號：{stock_id}\n\n"
            f"【三大法人近 {len(institutional)} 日買賣超（億元）】\n"
            f"外資累計：{totals['foreign_net']:+,.0f} 千股\n"
            f"投信累計：{totals['trust_net']:+,.0f} 千股\n"
            f"自營商累計：{totals['dealer_net']:+,.0f} 千股\n\n"
            f"【每日明細】\n"
            f"{json.dumps(institutional, ensure_ascii=False, indent=2)}\n\n"
        )

        if margin_trading:
            user += (
                f"【融資融券近 {len(margin_trading)} 日】\n"
                f"{json.dumps(list(margin_trading), ensure_ascii=False, indent=2)}\n\n"
            )
        else:
            user += "【融資融券】：本次無資料（需擴充 DB schema 後補齊）\n\n"

        if insider_holdings:
            user += (
                f"【董監持股變化】\n"
                f"{json.dumps(list(insider_holdings), ensure_ascii=False, indent=2)}\n\n"
            )
        else:
            user += "【董監持股】：本次無資料\n\n"

        user += "請根據以上資料給出籌碼面分析。"

        report = await self.llm.chat_structured(self._system, user, ChipReport)
        self.log.info(
            "chip done",
            stock_id=stock_id,
            trend=report.institutional_trend,
            score=report.chip_score,
        )
        return report


def _summarise_institutional(rows: list[dict]) -> dict:
    foreign_net = sum(r.get("foreign_net", 0) for r in rows)
    trust_net   = sum(r.get("trust_net",   0) for r in rows)
    dealer_net  = sum(r.get("dealer_net",  0) for r in rows)
    return {"foreign_net": foreign_net, "trust_net": trust_net, "dealer_net": dealer_net}
