from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "FinLab Stock Analyzer"
    app_version: str = "1.0.0"
    debug: bool = False

    # FinMind API
    finmind_api_url: str = "https://api.finmindtrade.com/api/v4/data"
    finmind_token: str = ""

    # LINE Notify
    line_notify_token: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./finlab.db"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
