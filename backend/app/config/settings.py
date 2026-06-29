from functools import lru_cache

from pydantic_settings import BaseSettings


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
    admin_secret: str = "finlab-admin-secret-2026"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
