from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database

from knowledge_base.config import load_settings


def get_db() -> Database:
    settings = load_settings()
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]

