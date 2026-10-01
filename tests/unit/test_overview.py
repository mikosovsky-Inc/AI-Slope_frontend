from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import SESSION, app

ID = str(uuid4())


@pytest.fixture
def overview():
    data = {
        "channel": dict(
            id=ID,
            name="Kanał",
            idea="Opis",
            status="active",
            language="pl",
            videos_per_day=2,
            budget_per_video_usd="0.2",
            autopilot_mode="semi_auto",
        ),
        "videos_by_status": {"READY": 2, "FUTURE & STATE": 1},
        "ideas_by_status": {"candidate": 5},
        "costs": dict(
            currency="USD",
            effective_usd="0.25",
            actual_usd="0.1",
            estimated_usd="0.5",
            pending_actual_events=2,
        ),
        "latest_plan": None,
    }
    state = {"status": 200, "calls": [], "data": data}

    def handler(request):
        state["calls"].append(request)
        assert request.headers["authorization"] == "Bearer synthetic"
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=dict(email="test@example.com", role="user"))
        assert request.url.path == f"/api/v1/channels/{ID}/overview"
        return httpx.Response(state["status"], json=state["data"])

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handler)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "synthetic", domain="testserver.local", path="/")
        yield client, state
        client.portal.call(http.aclose)


def test_empty_plan_and_exact_costs(overview):
    client, state = overview
    response = client.get(f"/channels/{ID}/overview")
    assert response.status_code == 200
    assert "nie zapisał jeszcze planu" in response.text
    assert "0.25 USD" in response.text
    assert "FUTURE+%26+STATE" in response.text
    assert "candidate" in response.text
    assert all(call.method == "GET" for call in state["calls"])


@pytest.mark.parametrize("status", ["waiting_approval", "blocked", "complete", "future"])
def test_plan_states_dates_and_escaping(overview, status):
    client, state = overview
    state["data"]["latest_plan"] = dict(
        day="2025-01-01", status=status, target=3, reason="<script>unsafe</script>"
    )
    response = client.get(f"/channels/{ID}/overview")
    assert response.status_code == 200
    assert "2025-01-01" in response.text and "3 filmów" in response.text
    assert "&lt;script&gt;unsafe" in response.text
    assert ("Przejrzyj pomysły do zatwierdzenia" in response.text) == (status == "waiting_approval")
    assert "może pochodzić z wcześniejszego dnia" in response.text


@pytest.mark.parametrize("status", [401, 403, 404, 503])
def test_errors(overview, status):
    client, state = overview
    state["status"] = status
    response = client.get(f"/channels/{ID}/overview", follow_redirects=False)
    assert response.status_code == (303 if status == 401 else status)
    if status == 401:
        assert response.headers["location"] == "/login"
        assert SESSION not in client.cookies


def test_malformed_and_anonymous(overview):
    client, state = overview
    state["data"] = {}
    assert client.get(f"/channels/{ID}/overview").status_code == 503
    client.cookies.clear()
    state["calls"].clear()
    assert client.get(f"/channels/{ID}/overview", follow_redirects=False).status_code == 303
    assert not state["calls"]
