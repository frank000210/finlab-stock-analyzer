from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    vault_path: Path


def load_settings() -> Settings:
    return Settings(
        mongo_uri=os.getenv("KB_MONGO_URI", "mongodb://localhost:27017"),
        mongo_db=os.getenv("KB_MONGO_DB", "knowledge_base"),
        vault_path=Path(os.getenv("KB_VAULT_PATH", "./vault")).resolve(),
    )

