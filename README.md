# TradingAgents-TW

台股多代理人 LLM 選股系統。多個 AI Agent 協作分析基本面、技術面、籌碼面、情緒面與新聞面，每日收盤後自動產出選股報告。

```
收盤後 15:30
    Go data-collector ─── FinMind API ──→ PostgreSQL
                      ─── PTT 爬蟲   ──→ PostgreSQL
                      ─── 新聞 RSS   ──→ PostgreSQL
                      ─── Redis Pub  ──→ Python orchestrator

    Python orchestrator (asyncio)
        ├── 技術分析師   ─┐
        ├── 基本面分析師  ├─→ Researcher 辯論 ─→ Trader ─→ Risk ─→ 報告
        ├── 籌碼分析師   ─┤
        ├── 情緒分析師   ─┘
        └── 新聞分析師   ─┘
```

---

## 前置需求

- Docker Desktop（PostgreSQL + Redis）
- Go 1.22+
- Python 3.11+（由 [uv](https://docs.astral.sh/uv/) 管理，自動安裝）
- FinMind API Token（免費註冊：[finmindtrade.com](https://finmindtrade.com)）
- 至少一個 LLM API Key（Gemini / Claude / OpenAI，擇一即可）

安裝 uv（若尚未安裝）：

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## 快速啟動

### 1. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`，至少填入：

```env
# 選擇你的 LLM（擇一）
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash
GEMINI_API_KEY=your-key

# FinMind
FINMIND_API_TOKEN=your-token
```

### 2. 啟動資料庫

```bash
docker compose up -d
```

PostgreSQL 會自動執行 `scripts/init_db.sql` 建立所有 table。

### 3. 安裝 Go 依賴並測試爬蟲

```bash
cd data-collector
go mod tidy
go run ./cmd/main.go --run-now   # 立即執行一次所有收集任務
```

`--run-now` 會：拉取 FinMind 股價 + 三大法人、爬 PTT、爬新聞，完成後發 Redis 訊號。

正式排程模式（背景執行）：

```bash
go run ./cmd/main.go   # 15:30 股價/法人、每小時 PTT、每2小時新聞
```

### 4. 安裝 Python 依賴

```bash
cd agents
uv sync          # 建立 .venv 並安裝所有依賴
uv sync --group dev  # 含開發依賴（pytest、ipython）
```

### 5. 執行 Python orchestrator

```bash
cd agents
uv run python main.py
```

等待 Redis 訊號後自動觸發分析，或直接測試 LLM 連線：

```bash
cd agents
uv run python -c "
import asyncio
from llm.factory import create_provider_from_settings

async def test():
    llm = create_provider_from_settings()
    reply = await llm.chat('你是助手', '請用一句話介紹台積電')
    print(reply)

asyncio.run(test())
"
```

---

## 切換 LLM

只改 `.env`，程式碼不需要動：

```env
# Gemini（預設）
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash

# 切換到 Claude
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-6

# 切換到 OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

---

## 專案結構

```
tradingagents-tw/
├── docker-compose.yml          # PostgreSQL 16 + Redis 7
├── .env.example                # 所有環境變數範本
├── scripts/
│   └── init_db.sql             # DB schema
│
├── data-collector/             # Go：資料收集
│   ├── cmd/main.go             # 啟動入口（支援 --run-now）
│   └── internal/
│       ├── finmind/            # FinMind API（retry x3）
│       ├── ptt/                # PTT Stock 板爬蟲
│       ├── news/               # RSS 新聞爬蟲
│       ├── scheduler/          # cron 排程
│       ├── db/                 # PostgreSQL upsert
│       └── redis/              # 資料就緒訊號
│
└── agents/                     # Python：LLM Agent
    ├── main.py                 # 入口，監聽 Redis 並觸發分析
    ├── config.py               # 設定（pydantic-settings）
    ├── llm/                    # LLM 抽象層
    │   ├── base.py             # BaseLLMProvider 介面
    │   ├── gemini.py           # Google Gemini
    │   ├── claude.py           # Anthropic Claude
    │   ├── openai_provider.py  # OpenAI
    │   └── factory.py          # create_provider()
    ├── agents/
    │   ├── models.py           # 所有 Pydantic 輸出模型
    │   ├── base.py             # BaseAgent
    │   ├── technical_analyst.py
    │   ├── fundamental_analyst.py
    │   ├── sentiment_analyst.py
    │   ├── news_analyst.py
    │   └── chip_analyst.py
    ├── tools/
    │   ├── db.py               # SQLAlchemy async 查詢
    │   └── indicators.py       # pandas-ta 指標計算
    └── prompts/                # System prompt（.txt），與程式碼分離
```

---

## 開發階段

| Phase | 狀態 | 說明 |
|-------|------|------|
| Phase 1 | ✅ 完成 | Docker、Go 爬蟲、DB、LLM 抽象層 |
| Phase 2 | ✅ 完成 | 5 個 Analyst Agent |
| Phase 3 | ✅ 完成 | Researcher 辯論、Trader、Risk、Orchestrator、報告輸出 |
| Phase 4 | ✅ 完成 | Backtrader 回測、績效指標、基本面資料補全 |

---

## 回測

回測使用 `daily_recommendations` 表中已核准的訊號，對歷史股價做信號重播。

**前置條件**：需先有資料（Go collector 拉過歷史資料）且已有 Agent 跑過的選股建議。

```bash
cd agents

# 回測過去一年（預設）
uv run python ../scripts/backtest.py

# 指定期間與個股
uv run python ../scripts/backtest.py --start 2024-01-01 --end 2024-12-31 --stocks 2330,2454,2382

# 指定初始資金（預設 100 萬）
uv run python ../scripts/backtest.py --start 2024-01-01 --end 2024-12-31 --cash 5000000

# 輸出 Markdown 報告
uv run python ../scripts/backtest.py --output reports/my_backtest.md
```

回測輸出指標：總報酬率、年化報酬、夏普比率、最大回撤、勝率、獲利因子。

---

## 風控硬性規則

- 單一個股最高倉位：20%
- 最大持股數：10 檔
- 整體虧損 > 10% 時全面降倉
- Phase 1-2：`DRY_RUN=true`，只產報告不下單
