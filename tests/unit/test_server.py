import pytest
from fastapi.testclient import TestClient

from main import Settings, app, get_settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/app"])
def test_serves_html_without_backend(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "auth-form" in response.text


def test_public_config(client):
    response = client.get("/config")
    assert response.json() == {"api_base_url": "https://api.example.com"}
    assert response.headers["cache-control"] == "no-store"


def test_assets_and_private_files(client):
    assert client.get("/assets/scripts/app.js").status_code == 200
    assert client.get("/assets/styles/main.css").status_code == 200
    for path in ["/.env", "/main.py", "/assets/%2e%2e/main.py", "/api/v1/auth/setup"]:
        assert client.get(path).status_code == 404


def test_frontend_config_does_not_require_database_or_jwt():
    settings = Settings(_env_file=None)
    assert set(type(settings).model_fields) == {"api_base_url"}
