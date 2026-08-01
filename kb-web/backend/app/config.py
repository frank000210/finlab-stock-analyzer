from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kb_mongo_uri: str = "mongodb://localhost:27017"
    kb_mongo_db: str = "knowledge_base"
    kb_web_password: str = ""
    kb_api_token: str = ""
    jwt_secret: str = "dev-secret-change-me"
    anthropic_api_key: str = ""
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
