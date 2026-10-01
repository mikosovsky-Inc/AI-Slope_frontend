import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import CSRF, SESSION, app, get_settings


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://backend.test")
    get_settings.cache_clear()
    state = {"first": False, "error": None, "calls": []}

    def handle(request):
        state["calls"].append(request)
        if state["error"]:
            return httpx.Response(state["error"], json={"detail": "private upstream error"})
        path = request.url.path
        if path.endswith("/dashboard"):
            return httpx.Response(
                200,
                json={
                    "channels": 0,
                    "active_channels": 0,
                    "videos": 0,
                    "videos_by_status": {},
                    "recent_videos": [],
                    "costs": {
                        "currency": "USD",
                        "effective_usd": "0",
                        "actual_usd": "0",
                        "estimated_usd": "0",
                        "pending_actual_events": 0,
                    },
                },
            )
        if path.endswith("/setup"):
            return httpx.Response(200, json={"registration_required": state["first"]})
        if path.endswith("/login"):
            return httpx.Response(200, json={"access_token": "test-token", "expires_in": 1800})
        if path.endswith("/register"):
            return httpx.Response(201, json={"id": "user-id"})
        if path.endswith("/me"):
            return httpx.Response(200, json={"email": "creator@example.com", "role": "admin"})
        raise AssertionError(path)

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        yield client, state
        client.portal.call(http.aclose)
    get_settings.cache_clear()


def form(client, path="/login"):
    response = client.get(path)
    return {
        "csrf": re.search(r'name="csrf" value="([^"]+)"', response.text)[1],
        "email": "creator@example.com",
        "password": "long-test-password",
    }


def test_first_account_and_existing_studio(studio):
    client, state = studio
    assert 'action="/login"' in client.get("/").text
    state["first"] = True
    response = client.get("/")
    assert 'action="/register"' in response.text
    assert "administratora" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_login_cookie_authenticated_page_and_logout(studio):
    client, state = studio
    response = client.post("/login", data=form(client), follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Max-Age=1800" in response.headers["set-cookie"]
    page = client.get("/app")
    assert "creator@example.com" in page.text
    assert "test-token" not in page.text
    assert state["calls"][-1].headers["authorization"] == "Bearer test-token"
    client.post("/logout", data={"csrf": client.cookies[CSRF]})
    assert SESSION not in client.cookies


def test_registration_confirmation_and_payload(studio):
    client, state = studio
    data = form(client, "/register")
    response = client.post("/register", data=data | {"confirm_password": "different"})
    assert response.status_code == 422
    assert not any(r.method == "POST" for r in state["calls"])
    data["csrf"] = client.cookies[CSRF]
    response = client.post("/register", data=data | {"confirm_password": data["password"]})
    assert "Konto utworzone" in response.text
    assert "confirm_password" not in state["calls"][-1].content.decode()
    assert data["password"] not in response.text


@pytest.mark.parametrize("path", ["/login", "/register", "/logout"])
def test_csrf_blocks_posts(studio, path):
    client, state = studio
    assert client.post(path, data={"csrf": "forged"}).status_code == 403
    assert state["calls"] == []


@pytest.mark.parametrize("status", [401, 409, 422, 429, 500])
def test_safe_api_errors(studio, status):
    client, state = studio
    data = form(client)
    state["error"] = status
    response = client.post("/login", data=data)
    assert response.status_code == (503 if status == 500 else status)
    assert "private upstream error" not in response.text
    assert data["password"] not in response.text


def test_outage_is_not_empty_database(studio):
    client, state = studio
    state["error"] = 503
    response = client.get("/")
    assert response.status_code == 503
    assert 'action="/register"' not in response.text
    assert "SPRÓBUJ PONOWNIE" in response.text


def test_assets_and_private_files(studio):
    client, _ = studio
    for path in ["/assets/styles/main.css", "/assets/scripts/app.js", "/apple-touch-icon.png"]:
        assert client.get(path).status_code == 200
    for path in ["/.env", "/main.py", "/config", "/api/v1/auth/setup"]:
        assert client.get(path).status_code == 404


def test_expired_session_cleared(studio):
    client, _ = studio
    client.cookies.set(SESSION, "expired", domain="testserver.local", path="/")

    def handle(request):
        if request.url.path.endswith("/me"):
            return httpx.Response(401)
        return httpx.Response(200, json={"registration_required": False})

    http = httpx.AsyncClient(base_url="http://backend.test", transport=httpx.MockTransport(handle))
    app.state.backend = BackendClient(http)
    assert 'action="/login"' in client.get("/app").text
    assert SESSION not in client.cookies
    client.portal.call(http.aclose)
