from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    kb_mongo_uri: str = "mongodb://localhost:27017"
    kb_mongo_db: str = "knowledge_base"
    kb_web_password: str = ""
    kb_api_token: str = ""
    jwt_secret: str = "dev-secret-change-me"

    # LLM: OpenCode Go, OpenAI-compatible /chat/completions. Same gateway
    # already used (and proven in production) by the main finlab backend --
    # see backend/app/llm/client.py. Accepts both env var spellings since
    # the main app's Zeabur config uses OPENCODE_APIKEY (no underscore)
    # while local dev conventionally uses OPENCODE_API_KEY.
    opencode_api_key: str = Field(
        default="", validation_alias=AliasChoices("OPENCODE_API_KEY", "OPENCODE_APIKEY")
    )
    llm_base_url: str = "https://opencode.ai/zen/go/v1"
    llm_model: str = "minimax-m2.5"
    llm_fallback_model: str = "qwen3.7-plus"
    llm_timeout_seconds: float = 90.0
    # NN2: kb-web shares the OpenCode key with the main finlab backend, so a
    # bug or abuse loop here could burn through the account's shared quota.
    # Cap kb-web's own contribution independently of the main app's limit.
    llm_daily_call_limit: int = 100

    # PP1: 查詢改寫——問句展開成 2-3 組檢索詞提升檢索精度，消耗 1 次 LLM 額度。
    # 設 False 可退回舊的單查詢模式（測試 / 省 quota 用）。
    enable_query_rewrite: bool = True
    # PP3: agentic 迴圈最大輪數（每輪 1 次 LLM 呼叫 + 工具執行）。
    # 最大值 = 5，含初始回答最多 5 次 LLM call / question。
    max_agent_rounds: int = 3
    # PP4: 是否允許模型使用 web_search / fetch_url 工具。
    enable_web_search: bool = True

    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.jwt_secret == "dev-secret-change-me":
        logger.warning(
            "KB_WEB JWT_SECRET is the insecure default. "
            "Set JWT_SECRET env var before production deployment."
        )
    if not s.opencode_api_key:
        logger.warning(
            "OPENCODE_API_KEY / OPENCODE_APIKEY is not set. "
            "LLM calls will fail until this is configured."
        )
    return s
