import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    app_name: str = "FinLab Stock Analyzer"
    app_version: str = "1.0.0"
    debug: bool = False

    # FinMind API
    finmind_api_url: str = "https://api.finmindtrade.com/api/v4/data"
    finmind_token: str = ""

    # LINE Notify
    line_notify_token: str = ""

    # LLM（OpenCode Go，OpenAI 相容）。key 一律走環境變數，不進版控。
    # 供應商中立：換服務只要改 base_url/model，程式碼不用動。
    opencode_api_key: str = ""
    llm_base_url: str = "https://opencode.ai/zen/go/v1"
    # minimax-m2.5：實測 5 個模型後選定——延遲 ~15s、輸出結構完整、能正確
    # 指出財報數據矛盾；deepseek-v4-flash/glm-5.1 會回空內容，kimi 會把思考
    # 過程洩漏到答案裡，qwen3.7-plus 要 40s 且 token 用量 2.5 倍。
    llm_model: str = "minimax-m2.5"
    llm_fallback_model: str = "qwen3.7-plus"
    llm_timeout_seconds: float = 90.0
    llm_daily_call_limit: int = 200

    # Admin / OAuth
    google_client_id: str = ""
    # No hardcoded fallback: get_settings() below fills in a random
    # per-process secret if this is left unset, and logs a warning.
    admin_secret: str = ""
    # Comma-separated, single source of truth for the default admin
    # whitelist (mirrors the `cors_origins` convention). The live/editable
    # list still lives in Mongo settings (`allowed_admin_emails`); this is
    # only the fallback used when that store has nothing set yet.
    allowed_admin_emails: str = "frank210@gmail.com"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./finlab.db"

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "finlab"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def default_allowed_admins(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_admin_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.admin_secret:
        # Never fall back to a hardcoded secret. Generate a random one for
        # this process instead so a missing ADMIN_SECRET fails safe (all
        # existing admin tokens/sessions are invalidated) rather than
        # silently accepting a secret anyone can read in the source code.
        settings.admin_secret = secrets.token_hex(32)
        logger.warning(
            "ADMIN_SECRET is not set. Generated a random per-process secret; "
            "admin sessions will be invalidated on every restart until you "
            "set ADMIN_SECRET in the environment."
        )
    if not settings.finmind_token:
        # R9：FinMind 是全站絕大多數端點（分析/籌碼/風控...）的主要資料源，
        # 沒有 token 就只能用免費/未驗證額度，額度用完後會在各端點分散出現
        # 零星的 500/502，難以追查根因。啟動時就給一個清楚的警告，跟
        # ADMIN_SECRET 的待遇一致，而不是等使用者回報「某某頁面壞了」才發現。
        logger.warning(
            "FINMIND_TOKEN is not set. FinMind requests will fall back to "
            "unauthenticated/free-tier rate limits, which most endpoints in "
            "this app depend on — set FINMIND_TOKEN in the environment."
        )
    return settings
