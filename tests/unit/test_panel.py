import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import SESSION, app


@pytest.fixture
def panel():
    state = {"status": 200, "calls": [], "malformed": False}
    dashboard = {
        "channels": 13,
        "active_channels": 2,
        "videos": 1,
        "videos_by_status": {"READY": 1, "FUTURE_STATUS": 3},
        "costs": {
            "currency": "USD",
            "effective_usd": "0.2700",
            "actual_usd": "0.1500",
            "estimated_usd": "0.6200",
            "pending_actual_events": 1,
        },
        "recent_videos": [
            {"title": "<script>alert(1)</script>", "status": "READY", "language": "pl"}
        ],
    }

    def handle(request):
        state["calls"].append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json={"email": "owner@example.com", "role": "user"})
        if state["status"] != 200:
            return httpx.Response(state["status"], json={"detail": "private"})
        if state["malformed"]:
            return httpx.Response(200, json={})
        if request.url.path.endswith("/dashboard"):
            return httpx.Response(200, json=dashboard)
        offset = int(request.url.params["offset"])
        assert request.url.params["limit"] == "12"
        return httpx.Response(
            200,
            json={
                "total": 13,
                "limit": 12,
                "offset": offset,
                "items": [
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "name": "Kanał historyczny",
                        "idea": "Ciekawostki historyczne",
                        "status": "draft",
                        "language": "pl",
                        "videos_per_day": 2,
                        "budget_per_video_usd": "0.2",
                        "autopilot_mode": "manual",
                    }
                ]
                if offset < 13
                else [],
            },
        )

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "test-token", domain="testserver.local", path="/")
        yield client, state
        client.portal.call(http.aclose)


def test_dashboard_real_values_escaping_and_unknown_status(panel):
    client, _ = panel
    response = client.get("/app")
    assert response.status_code == 200
    for text in ["0.2700", "0.1500", "FUTURE_STATUS", "owner@example.com"]:
        assert text in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_channel_pagination(panel):
    client, _ = panel
    first = client.get("/channels")
    assert "Kanał historyczny" in first.text
    assert 'href="/channels?offset=12"' in first.text
    second = client.get("/channels?offset=12")
    assert 'href="/channels?offset=0"' in second.text
    assert "Następna" not in second.text
    assert "Brak kanałów na tej stronie" in client.get("/channels?offset=24").text
    assert client.get("/channels?offset=-1").status_code == 422


@pytest.mark.parametrize("path", ["/app", "/channels"])
def test_missing_session_never_calls_backend(panel, path):
    client, state = panel
    client.cookies.clear()
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert state["calls"] == []


@pytest.mark.parametrize("status", [401, 403, 503])
@pytest.mark.parametrize("path", ["/app", "/channels"])
def test_error_does_not_become_fake_empty_state(panel, path, status):
    client, state = panel
    state["status"] = status
    response = client.get(path, follow_redirects=False)
    if status == 401:
        assert response.status_code == 303
        assert SESSION not in client.cookies
    else:
        assert response.status_code == status
        assert "Dane są niedostępne" in response.text
        assert "Jeszcze nie masz kanałów" not in response.text
        assert SESSION in client.cookies
    assert "private" not in response.text


def test_malformed_contract_is_service_error(panel):
    client, state = panel
    state["malformed"] = True
    assert client.get("/app").status_code == 503
