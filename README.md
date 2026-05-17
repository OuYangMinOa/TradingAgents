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
- Python 3.11+
- FinMind API Token（免費註冊：[finmindtrade.com](https://finmindtrade.com)）
- 至少一個 LLM API Key（Gemini / Claude / OpenAI，擇一即可）

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
pip install -r requirements.txt
```

### 5. 執行 Python orchestrator

```bash
cd agents
python main.py
```

等待 Redis 訊號後自動觸發分析（Phase 2 開始後），或直接測試單一 Agent：

```bash
python -c "
import asyncio
from llm.factory import create_provider_from_settings
from agents.technical_analyst import TechnicalAnalyst

async def test():
    llm = create_provider_from_settings()
    agent = TechnicalAnalyst(llm)
    # 需要先有 DB 資料
    print(repr(llm))

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
| Phase 2 | 🔨 進行中 | 5 個 Analyst Agent |
| Phase 3 | ⏳ 待開始 | Researcher 辯論、Trader、Risk、Orchestrator |
| Phase 4 | ⏳ 待開始 | Backtrader 回測、Prompt 調優 |

---

## 風控硬性規則

- 單一個股最高倉位：20%
- 最大持股數：10 檔
- 整體虧損 > 10% 時全面降倉
- Phase 1-2：`DRY_RUN=true`，只產報告不下單
