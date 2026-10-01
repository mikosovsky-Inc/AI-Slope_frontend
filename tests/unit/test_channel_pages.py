import json
import re
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import CSRF, SESSION, app

CHANNEL = str(uuid4())
TASK = str(uuid4())
DATA = {
    "name": "Historia",
    "idea": "Polskie ciekawostki historyczne",
    "language": "pl",
    "videos_per_day": "2",
    "budget_per_video_usd": "0.2000",
    "autopilot_mode": "manual",
}


@pytest.fixture
def studio():
    state = {"calls": [], "error": None, "task_status": "queued", "eager": False}
    channel = DATA | {
        "id": CHANNEL,
        "status": "draft",
        "blueprint": {"configuration": {"niche_description": ""}, "content_pillars": []},
    }

    def handle(request):
        state["calls"].append(request)
        path = request.url.path
        if path == "/openapi.json":
            return httpx.Response(
                200,
                json={
                    "components": {
                        "schemas": {
                            "ChannelCreate": {"properties": {"language": {"enum": ["pl", "en"]}}},
                            "AutopilotMode": {"enum": ["manual", "semi_auto", "future_mode"]},
                        }
                    }
                },
            )
        assert request.headers["authorization"] == "Bearer fake-token"
        if path.endswith("/me"):
            return httpx.Response(200, json={"email": "owner@example.com", "role": "user"})
        if request.method != "GET" and state["error"]:
            return httpx.Response(state["error"], json={"detail": "sensitive upstream error"})
        if path.endswith("/analyze"):
            assert request.headers["idempotency-key"]
            if state["eager"]:
                return httpx.Response(200, json=channel)
            return httpx.Response(202, json={"id": TASK, "kind": "analyze", "status": "queued"})
        if "/tasks/" in path:
            if state.get("complete_during_read"):
                channel["name"] = "Kanał po zakończeniu analizy"
            return httpx.Response(
                200, json={"id": TASK, "kind": "analyze", "status": state["task_status"]}
            )
        return httpx.Response(201 if request.method == "POST" else 200, json=channel)

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "fake-token", domain="testserver.local", path="/")
        yield client, state
        client.portal.call(http.aclose)


def test_create_uses_contract_and_redirects(studio):
    client, state = studio
    page = client.get("/channels/new")
    assert page.status_code == 200
    assert 'value="future_mode"' in page.text
    response = client.post(
        "/channels/new", data=DATA | {"csrf": client.cookies[CSRF]}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/channels/{CHANNEL}"
    sent = json.loads(state["calls"][-1].content)
    assert sent["videos_per_day"] == 2
    assert sent["budget_per_video_usd"] == "0.2000"
    assert "csrf" not in sent


def test_settings_do_not_replace_blueprint(studio):
    client, state = studio
    client.get(f"/channels/{CHANNEL}")
    client.post(
        f"/channels/{CHANNEL}/settings",
        data=DATA | {"csrf": client.cookies[CSRF]},
        follow_redirects=False,
    )
    assert state["calls"][-1].method == "PATCH"
    assert "blueprint" not in json.loads(state["calls"][-1].content)


@pytest.mark.parametrize("error", [409, 422, 503])
def test_save_error_retains_values_without_raw_error(studio, error):
    client, state = studio
    client.get("/channels/new")
    state["error"] = error
    response = client.post("/channels/new", data=DATA | {"csrf": client.cookies[CSRF]})
    assert response.status_code == error
    assert DATA["idea"] in response.text
    assert "sensitive upstream" not in response.text


def test_csrf_blocks_mutation(studio):
    client, state = studio
    assert client.post("/channels/new", data=DATA).status_code == 403
    assert state["calls"] == []


@pytest.mark.parametrize("eager", [False, True])
def test_analysis_accepts_async_and_eager_preserves_idempotency(studio, eager):
    client, state = studio
    state["eager"] = eager
    page = client.get(f"/channels/{CHANNEL}")
    key = re.search(r'name="key" value="([^"]+)"', page.text)[1]
    data = {"csrf": client.cookies[CSRF], "key": key}
    response = client.post(f"/channels/{CHANNEL}/analyze", data=data, follow_redirects=False)
    assert response.status_code == 303
    assert (f"task_id={TASK}" in response.headers["location"]) is (not eager)
    assert state["calls"][-1].headers["idempotency-key"] == key


@pytest.mark.parametrize("status", ["queued", "running", "succeeded", "failed", "needs_review"])
def test_task_status_and_manual_refresh(studio, status):
    client, state = studio
    state["task_status"] = status
    response = client.get(f"/channels/{CHANNEL}?task_id={TASK}")
    assert response.status_code == 200
    assert f"Stan zadania: {status}" in response.text
    assert client.get(f"/task-status/{TASK}").json() == {"status": status}


def test_unauthenticated_pages_and_poll(studio):
    client, state = studio
    client.cookies.clear()
    assert client.get("/channels/new", follow_redirects=False).status_code == 303
    assert client.get(f"/task-status/{TASK}").status_code == 401
    assert state["calls"] == []


def test_csrf_remains_valid_across_tabs(studio):
    client, _ = studio
    client.get("/channels/new")
    csrf = client.cookies[CSRF]
    client.get(f"/channels/{CHANNEL}")
    assert client.cookies[CSRF] == csrf


def test_page_includes_channel_changes_committed_when_task_completes(studio):
    client, state = studio
    state["task_status"] = "succeeded"
    state["complete_during_read"] = True
    response = client.get(f"/channels/{CHANNEL}?task_id={TASK}")
    assert "Stan zadania: succeeded" in response.text
    assert "Kanał po zakończeniu analizy" in response.text


@pytest.mark.parametrize("status", [None, 123, [], ""])
def test_poll_rejects_invalid_backend_status(studio, status):
    client, state = studio
    state["task_status"] = status
    response = client.get(f"/task-status/{TASK}")
    assert response.status_code == 502
    assert "status" not in response.json()
