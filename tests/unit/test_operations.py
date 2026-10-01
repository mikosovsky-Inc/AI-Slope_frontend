import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import CSRF, SESSION, app

V, T, R, S, U, C = (str(uuid4()) for _ in range(6))


@pytest.fixture
def studio():
    state = {"calls": [], "role": "admin", "format": "story", "error": None}
    scene = dict(
        id=S,
        position=1,
        duration="5",
        narration="Tekst",
        visual_prompt="Las",
        visual_type="image",
        mood="calm",
        caption_emphasis=[],
        camera_motion="static",
    )

    def handle(req):
        state["calls"].append(req)
        path = req.url.path
        if path == "/openapi.json":
            return httpx.Response(
                200,
                json={
                    "components": {
                        "schemas": {
                            "TaskStatus": {"enum": ["failed", "running"]},
                            "TaskKind": {"enum": ["render"]},
                            "RecoveryInput": {
                                "properties": {
                                    "action": {"enum": ["resume", "use_asset", "abandon"]}
                                }
                            },
                            "RevisionPatch": {
                                "properties": {
                                    "camera_motion": {
                                        "anyOf": [{"enum": ["static", "zoom_in"]}, {"type": "null"}]
                                    }
                                }
                            },
                        }
                    }
                },
            )
        assert req.headers["authorization"] == "Bearer test-token"
        if req.method != "GET":
            return httpx.Response(state["error"] or 202, json={})
        if path.endswith("/me"):
            value = dict(id=U, email="test@example.com", role=state["role"])
        elif path.endswith("/recoveries"):
            value = [
                dict(number=1, action="resume", note="<script>bad</script>", created_at="today")
            ]
        elif path.endswith("/revisions"):
            value = [
                dict(
                    id=R,
                    number=2,
                    status="draft",
                    final_asset_id=None,
                    scenes=[scene],
                    created_at="today",
                )
            ]
        elif path.endswith("/assets"):
            value = []
        elif path.endswith("/budget"):
            value = dict(currency="USD", limit_usd="10", committed_usd="2", remaining_usd="8")
        elif path.endswith("/costs"):
            cost = dict(
                video_id=V,
                provider="mock",
                operation="render",
                model="mock",
                estimated_cost_usd="1",
                created_at="today",
            )
            value = dict(
                summary=dict(
                    currency="USD",
                    effective_usd="1",
                    actual_usd="0",
                    estimated_usd="2",
                    pending_actual_events=1,
                ),
                items=[cost | {"actual_cost_usd": None}, cost | {"actual_cost_usd": "0"}],
                total=22,
                limit=20,
                offset=0,
            )
        elif path.endswith("/jobs"):
            value = dict(
                items=[
                    dict(
                        id=T,
                        owner_id=U,
                        video_id=V,
                        kind="render",
                        status="failed",
                        attempts=1,
                        max_attempts=3,
                        queue="render",
                        request_id=None,
                    )
                ],
                total=21,
                limit=20,
                offset=0,
                counts={"failed": 21},
            )
        elif "/tasks/" in path:
            value = dict(id=T, video_id=V, kind="render", status="failed", attempts=1)
        elif "/channels/" in path:
            value = dict(id=C, name="Kanał")
        else:
            value = dict(
                id=V,
                title="Film",
                status="READY",
                language="pl",
                format=state["format"],
                duration_target=45,
                budget_limit_usd="10",
            )
        return httpx.Response(200, json=value)

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "test-token", domain="testserver.local", path="/")
        yield client, state
        client.portal.call(http.aclose)


def test_costs_and_budget(studio):
    client, _ = studio
    response = client.get(f"/channels/{C}/costs")
    assert response.status_code == 200
    assert "oczekuje" in response.text and "0 USD" in response.text
    assert "?offset=20" in response.text
    assert "Pozostało: 8 USD" in client.get(f"/videos/{V}/budget").text


def test_jobs_filters_and_gate(studio):
    client, state = studio
    response = client.get("/jobs?status=failed&video_id=&kind=render")
    assert response.status_code == 200
    assert f"/tasks/{T}" in response.text
    assert "kind=render" in response.text
    state["role"] = "user"
    state["calls"].clear()
    assert client.get("/jobs").status_code == 403
    assert not any(r.url.path.endswith("/jobs") for r in state["calls"])


@pytest.mark.parametrize("action", ["retry", "resume", "use_asset", "abandon"])
def test_recovery_mapping(studio, action):
    client, state = studio
    assert "&lt;script&gt;" in client.get(f"/tasks/{T}").text
    data = {"csrf": client.cookies[CSRF], "action": action, "note": "Sprawdzono"}
    if action == "use_asset":
        data["asset_id"] = S
    if action == "abandon":
        data["confirmed"] = "yes"
    response = client.post(
        f"/tasks/{T}/" + ("retry" if action == "retry" else "recover"),
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303
    last = state["calls"][-1]
    body = json.loads(last.content)
    assert body == (
        {"task_id": T}
        if action == "retry"
        else {k: v for k, v in data.items() if k not in ("csrf", "confirmed")}
    )


def test_confirm_csrf_and_preserved_failure(studio):
    client, state = studio
    client.get(f"/tasks/{T}")
    assert client.post(f"/tasks/{T}/retry", data={"csrf": "bad"}).status_code == 403
    response = client.post(
        f"/tasks/{T}/recover",
        data={"csrf": client.cookies[CSRF], "action": "abandon", "note": "Ważna notatka"},
    )
    assert response.status_code == 422 and "Ważna notatka" in response.text
    assert not any(r.method != "GET" for r in state["calls"])
    state["error"] = 409
    response = client.post(
        f"/tasks/{T}/recover",
        data={"csrf": client.cookies[CSRF], "action": "resume", "note": "Zachowaj"},
    )
    assert response.status_code == 409 and "Zachowaj" in response.text


@pytest.mark.parametrize("format", ["story", "top5"])
def test_revision_edit_and_cancel(studio, format):
    client, state = studio
    state["format"] = format
    assert client.get(f"/videos/{V}/revisions").status_code == 200
    data = dict(
        csrf=client.cookies[CSRF],
        narration="Nowa",
        visual_prompt="Nowy las",
        camera_motion="zoom_in",
    )
    url = f"/videos/{V}/revisions/{R}"
    assert client.post(url + f"/scenes/{S}", data=data, follow_redirects=False).status_code == 303
    last = state["calls"][-1]
    assert last.method == "PATCH"
    assert ("narration" in json.loads(last.content)) == (format == "story")
    assert client.post(url + "/cancel", data={"csrf": client.cookies[CSRF]}).status_code == 422
    assert (
        client.post(
            url + "/cancel",
            data={"csrf": client.cookies[CSRF], "confirmed": "yes"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert client.post(url + f"/scenes/{uuid4()}", data=data).status_code == 404


@pytest.mark.parametrize(
    "path", [f"/videos/{V}/budget", f"/tasks/{T}", "/jobs", f"/videos/{V}/revisions"]
)
def test_anonymous(studio, path):
    client, state = studio
    client.cookies.clear()
    assert client.get(path, follow_redirects=False).headers["location"] == "/login"
    assert not state["calls"]


@pytest.mark.parametrize("suffix", ["", f"/{R}/produce"])
def test_revision_start_routes(studio, suffix):
    client, state = studio
    client.get(f"/videos/{V}/revisions")
    response = client.post(
        f"/videos/{V}/revisions{suffix}",
        data={"csrf": client.cookies[CSRF]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert state["calls"][-1].url.path == f"/api/v1/videos/{V}/revisions{suffix}"
    assert state["calls"][-1].method == "POST"


def test_revision_error_keeps_edit(studio):
    client, state = studio
    client.get(f"/videos/{V}/revisions")
    state["error"] = 409
    response = client.post(
        f"/videos/{V}/revisions/{R}/scenes/{S}",
        data={
            "csrf": client.cookies[CSRF],
            "narration": "Nie zgub narracji",
            "visual_prompt": "Nie zgub obrazu",
            "camera_motion": "zoom_in",
        },
    )
    assert response.status_code == 409
    assert "Nie zgub narracji" in response.text and "Nie zgub obrazu" in response.text
