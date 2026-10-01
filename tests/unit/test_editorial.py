import re
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import CSRF, SESSION, app

CHANNEL, IDEA, TASK = (str(uuid4()) for _ in range(3))


@pytest.fixture
def studio():
    state = {
        "calls": [],
        "error": None,
        "idea_status": "candidate",
        "async": True,
        "task_status": "queued",
        "unsafe_url": False,
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
                            "IdeaStatus": {
                                "enum": ["candidate", "approved", "rejected", "used", "future"]
                            }
                        }
                    }
                },
            )
        assert request.headers["authorization"] == "Bearer test-token"
        if path.endswith("/me"):
            return httpx.Response(200, json={"email": "owner@example.com", "role": "user"})
        if state["error"] and request.method == "POST":
            return httpx.Response(state["error"], json={"detail": "private upstream error"})
        if request.method == "POST":
            if path.endswith(("/approve", "/reject")):
                return httpx.Response(200, json={"channel_id": CHANNEL})
            assert request.headers["idempotency-key"]
            return httpx.Response(
                202 if state["async"] else 200,
                json=(
                    {"kind": "ideas", "id": TASK, "status": "queued"}
                    if state["async"]
                    else {"items": [], "processed": 0}
                ),
            )
        if "/tasks/" in path:
            return httpx.Response(200, json={"id": TASK, "status": state["task_status"]})
        if path.endswith("/ideas"):
            item = {
                "id": IDEA,
                "title": "<script>bad()</script>",
                "concept": "Historia",
                "content_pillar": "Odkrycia",
                "format": "story",
                "hook_idea": "Zagadka",
                "rationale": "Ciekawy temat",
                "novelty_heuristic": {"score": 0.8, "rationale": "Ocena"},
                "visual_potential_heuristic": {"score": 0.6, "rationale": "Sceny"},
                "status": state["idea_status"],
            }
            return httpx.Response(
                200, json={"items": [item], "total": 11, "limit": 10, "offset": 0}
            )
        if path.endswith("/competitors"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "name": "Benchmark",
                            "platform": "youtube",
                            "url": "javascript:alert(1)"
                            if state["unsafe_url"]
                            else "https://example.com/history",
                            "niche": "Historia",
                            "example_titles": ["<img src=x>"],
                            "observed_formats": [],
                            "typical_length_seconds": None,
                            "publishing_frequency": "",
                            "notes": "",
                        }
                    ],
                    "total": 1,
                    "limit": 10,
                    "offset": 0,
                },
            )
        return httpx.Response(200, json={"id": CHANNEL, "name": "Kanał testowy"})

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "test-token", domain="testserver.local", path="/")
        yield client, state
        client.portal.call(http.aclose)


def test_idea_filter_pagination_and_escape(studio):
    client, state = studio
    response = client.get(f"/channels/{CHANNEL}/ideas?status=approved&offset=10")
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text
    assert "<script>bad()" not in response.text
    assert 'value="future"' in response.text
    assert "status=approved&amp;offset=0" in response.text
    assert state["calls"][-1].url.params["status"] == "approved"
    assert state["calls"][-1].url.params["offset"] == "10"


def test_competitor_source_and_url_validation(studio):
    client, state = studio
    response = client.get(f"/channels/{CHANNEL}/competitors")
    assert "Nie przeszukuje internetu" in response.text
    assert "&lt;img src=x&gt;" in response.text
    assert 'rel="noopener noreferrer"' in response.text
    state["unsafe_url"] = True
    assert client.get(f"/channels/{CHANNEL}/competitors").status_code == 503


@pytest.mark.parametrize("view,action", [("ideas", "generate"), ("competitors", "research")])
@pytest.mark.parametrize("is_async", [True, False])
def test_submission_preserves_key_and_async_redirect(studio, view, action, is_async):
    client, state = studio
    state["async"] = is_async
    page = client.get(f"/channels/{CHANNEL}/{view}")
    key = re.search(r'name="key" value="([^"]+)"', page.text)[1]
    response = client.post(
        f"/channels/{CHANNEL}/{view}/{action}",
        data={"csrf": client.cookies[CSRF], "key": key, "count": "12"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert ("task_id=" in response.headers["location"]) == is_async
    call = state["calls"][-1]
    assert call.headers["idempotency-key"] == key
    if view == "ideas":
        assert call.url.params["count"] == "12"
    else:
        assert call.url.path.endswith("/competitor-research")


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_decision_and_preserved_view(studio, action):
    client, _ = studio
    client.get(f"/channels/{CHANNEL}/ideas")
    response = client.post(
        f"/ideas/{IDEA}/{action}",
        data={
            "csrf": client.cookies[CSRF],
            "channel_id": CHANNEL,
            "status": "candidate",
            "offset": "10",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/channels/{CHANNEL}/ideas?offset=10&status=candidate"


def test_used_idea_has_no_decision_buttons(studio):
    client, state = studio
    state["idea_status"] = "used"
    text = client.get(f"/channels/{CHANNEL}/ideas").text
    assert "ZATWIERDŹ" not in text
    assert "ODRZUĆ" not in text


@pytest.mark.parametrize("status", [401, 403, 404, 409, 422, 503])
def test_mutation_errors_are_safe(studio, status):
    client, state = studio
    client.get(f"/channels/{CHANNEL}/ideas")
    state["error"] = status
    response = client.post(
        f"/ideas/{IDEA}/approve",
        data={"csrf": client.cookies[CSRF], "channel_id": CHANNEL},
        follow_redirects=False,
    )
    assert response.status_code == (303 if status == 401 else status)
    assert "private upstream error" not in response.text


def test_csrf_and_missing_auth_block_mutations(studio):
    client, state = studio
    assert client.post(f"/ideas/{IDEA}/reject").status_code == 403
    assert not state["calls"]
    client.cookies.clear()
    assert client.get(f"/channels/{CHANNEL}/ideas", follow_redirects=False).status_code == 303
    assert not state["calls"]


@pytest.mark.parametrize("status", ["queued", "succeeded", "failed", "needs_review"])
def test_task_states(studio, status):
    client, state = studio
    state["task_status"] = status
    response = client.get(f"/channels/{CHANNEL}/ideas?task_id={TASK}")
    assert f"Stan zadania: {status}" in response.text
