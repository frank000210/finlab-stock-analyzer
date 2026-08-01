import os

import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_module
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_login_lockout():
    auth_module._failed_attempts.clear()
    yield
    auth_module._failed_attempts.clear()


def test_login_wrong_password_returns_401():
    response = client.post("/api/login", json={"password": "wrong"})
    assert response.status_code == 401


def test_login_correct_password_returns_token():
    response = client.post("/api/login", json={"password": os.environ["KB_WEB_PASSWORD"]})
    assert response.status_code == 200
    assert "token" in response.json()


def test_login_locks_out_after_repeated_failures():
    for _ in range(auth_module._MAX_ATTEMPTS):
        client.post("/api/login", json={"password": "wrong"})

    response = client.post("/api/login", json={"password": os.environ["KB_WEB_PASSWORD"]})
    assert response.status_code == 429


def test_login_success_clears_lockout_counter():
    client.post("/api/login", json={"password": "wrong"})
    response = client.post("/api/login", json={"password": os.environ["KB_WEB_PASSWORD"]})
    assert response.status_code == 200


def test_protected_route_without_token_returns_401():
    response = client.get("/api/notebooks")
    assert response.status_code == 401


def test_protected_route_with_cli_token_succeeds():
    response = client.get(
        "/api/notebooks",
        headers={"Authorization": f"Bearer {os.environ['KB_API_TOKEN']}"},
    )
    assert response.status_code == 200


def test_health_endpoint_is_unauthenticated():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
