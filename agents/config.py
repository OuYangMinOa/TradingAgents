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

STOCK_META: dict[str, dict] = {
    "2330": {"name": "台積電",    "industry": "半導體"},
    "2317": {"name": "鴻海",      "industry": "電子製造"},
    "2454": {"name": "聯發科",    "industry": "IC設計"},
    "2308": {"name": "台達電",    "industry": "電子零組件"},
    "2881": {"name": "富邦金",    "industry": "金融"},
    "2882": {"name": "國泰金",    "industry": "金融"},
    "2412": {"name": "中華電",    "industry": "電信"},
    "2303": {"name": "聯電",      "industry": "半導體"},
    "3711": {"name": "日月光投控","industry": "半導體封測"},
    "2002": {"name": "中鋼",      "industry": "鋼鐵"},
    "1301": {"name": "台塑",      "industry": "石化"},
    "2886": {"name": "兆豐金",    "industry": "金融"},
    "2891": {"name": "中信金",    "industry": "金融"},
    "2357": {"name": "華碩",      "industry": "電腦及周邊"},
    "2382": {"name": "廣達",      "industry": "伺服器/筆電"},
}
