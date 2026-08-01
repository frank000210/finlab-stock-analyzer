import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("KB_MONGO_DB", "knowledge_base_test")
os.environ.setdefault("KB_WEB_PASSWORD", "test-password")
os.environ.setdefault("KB_API_TOKEN", "test-cli-token")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

import pytest
from pymongo import MongoClient


@pytest.fixture
def db():
    client = MongoClient(os.environ.get("KB_MONGO_URI", "mongodb://localhost:27017"))
    database = client[os.environ["KB_MONGO_DB"]]
    yield database
    client.drop_database(os.environ["KB_MONGO_DB"])
    client.close()
