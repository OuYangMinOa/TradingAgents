from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "gemini"       # gemini | claude | openai
    llm_model: str = "gemini-2.0-flash"

    # API Keys
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # FinMind
    finmind_api_token: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://tradingagents:tradingagents@localhost:5432/tradingagents"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Trading
    watchlist_mode: str = "custom"
    max_position_size: float = 0.20
    max_drawdown_limit: float = 0.10
    debate_rounds: int = 2
    dry_run: bool = True


settings = Settings()

WATCHLIST: list[str] = [
    "2330",  # 台積電
    "2317",  # 鴻海
    "2454",  # 聯發科
    "2308",  # 台達電
    "2881",  # 富邦金
    "2882",  # 國泰金
    "2412",  # 中華電
    "2303",  # 聯電
    "3711",  # 日月光投控
    "2002",  # 中鋼
    "1301",  # 台塑
    "2886",  # 兆豐金
    "2891",  # 中信金
    "2357",  # 華碩
    "2382",  # 廣達
]
