import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

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
    return settings
