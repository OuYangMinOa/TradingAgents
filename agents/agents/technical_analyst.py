import json

from agents.base import BaseAgent
from agents.models import TechnicalReport
from llm.base import BaseLLMProvider
from tools.indicators import calculate_indicators, estimate_support_resistance


class TechnicalAnalyst(BaseAgent):
    def __init__(self, llm: BaseLLMProvider) -> None:
        super().__init__(llm)
        self._system = self.load_prompt("technical")

    async def analyze(self, stock_id: str, ohlcv: list[dict]) -> TechnicalReport:
        self._log_call(stock_id)

        indicators = calculate_indicators(ohlcv)
        support, resistance = estimate_support_resistance(ohlcv)

        # Provide LLM with both raw indicators and recent price trend
        recent_closes = [round(r["close"], 2) for r in ohlcv[-15:]]

        user = (
            f"股票代號：{stock_id}\n"
            f"資料筆數：{len(ohlcv)} 個交易日\n\n"
            f"技術指標快照（最新值）：\n"
            f"{json.dumps(indicators, ensure_ascii=False, indent=2)}\n\n"
            f"近 15 日收盤價（舊→新）：{recent_closes}\n\n"
            f"近 20 日高低點：支撐 {support:.2f}，壓力 {resistance:.2f}\n\n"
            "請根據以上資料給出技術面分析。"
        )

        report = await self.llm.chat_structured(self._system, user, TechnicalReport)

        # Override support/resistance with calculated values if LLM returns 0
        if report.support_level == 0:
            report = report.model_copy(update={"support_level": round(support, 2)})
        if report.resistance_level == 0:
            report = report.model_copy(update={"resistance_level": round(resistance, 2)})

        self.log.info("technical done", stock_id=stock_id, signal=report.signal, trend=report.trend)
        return report
