from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import CSRF, SESSION, app, get_settings

VIDEO, SCENE, ASSET, TASK, IDEA, CHANNEL = (str(uuid4()) for _ in range(6))


@pytest.fixture
def studio(tmp_path, monkeypatch):
    import app.api.media as media

    original = media.NamedTemporaryFile
    monkeypatch.setattr(media, "NamedTemporaryFile", lambda **kw: original(dir=tmp_path, **kw))
    state = {
        "calls": [],
        "active": False,
        "status": "SCRIPT_READY",
        "format": "story",
        "error": None,
        "create_status": 202,
        "mime": "video/mp4",
    }

    def handle(request):
        state["calls"].append(request)
        path = request.url.path
        if path == "/openapi.json":
            return httpx.Response(
                200,
                json={"components": {"schemas": {"VideoStatus": {"enum": ["READY", "FUTURE"]}}}},
            )
        assert request.headers["authorization"] == "Bearer test-token"
        if path.endswith("/download"):
            if state["error"]:
                return httpx.Response(state["error"], content=b"secret backend detail")
            return httpx.Response(
                200, content=b"0123456789", headers={"content-type": state["mime"]}
            )
        if request.method != "GET":
            if state["error"]:
                return httpx.Response(state["error"], json={"detail": "private detail"})
            return httpx.Response(state["create_status"], json={"id": VIDEO})
        if path.endswith("/me"):
            return httpx.Response(200, json={"email": "owner@example.com", "role": "user"})
        if path.endswith("/status"):
            return httpx.Response(
                200,
                json={
                    "status": state["status"],
                    "updated_at": "2026-10-01",
                    "has_active_tasks": state["active"],
                    "tasks": [
                        {
                            "id": TASK,
                            "kind": "story",
                            "status": "running" if state["active"] else "succeeded",
                            "attempts": 1,
                        }
                    ],
                },
            )
        if path.endswith("/scenes"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": SCENE,
                        "position": 1,
                        "duration": "5",
                        "narration": "Narracja",
                        "visual_prompt": "Las nocą",
                        "visual_type": "image",
                        "mood": "spokojny",
                        "caption_emphasis": ["Las"],
                    }
                ],
            )
        if path.endswith("/assets"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": ASSET,
                        "scene_id": SCENE,
                        "type": "video",
                        "content_type": "video/mp4",
                        "size_bytes": 10,
                    }
                ],
            )
        video = {
            "id": VIDEO,
            "title": "Film testowy",
            "status": state["status"],
            "language": "pl",
            "format": state["format"],
            "duration_target": 45,
            "budget_limit_usd": "1",
        }
        if path.endswith("/videos"):
            return httpx.Response(
                200, json={"items": [video], "total": 11, "limit": 10, "offset": 0}
            )
        if "/channels/" in path:
            return httpx.Response(200, json={"id": CHANNEL, "name": "Kanał"})
        return httpx.Response(200, json=video)

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "test-token", domain="testserver.local", path="/")
        yield client, state, tmp_path
        client.portal.call(http.aclose)


@pytest.mark.parametrize("code", [200, 201, 202])
def test_create_uses_only_create_endpoint(studio, code):
    client, state, _ = studio
    client.get(f"/videos/{VIDEO}")
    state["calls"].clear()
    state["create_status"] = code
    response = client.post(
        f"/ideas/{IDEA}/create-video", data={"csrf": client.cookies[CSRF]}, follow_redirects=False
    )
    assert response.headers["location"] == f"/videos/{VIDEO}"
    assert len(state["calls"]) == 1
    assert state["calls"][0].url.path.endswith("/create-video")


def test_list_filter_and_active_state(studio):
    client, state, _ = studio
    response = client.get(f"/channels/{CHANNEL}/videos?status=READY&offset=10")
    assert response.status_code == 200
    assert 'value="FUTURE"' in response.text
    assert state["calls"][-1].url.params["status"] == "READY"
    state["active"] = True
    response = client.get(f"/videos/{VIDEO}")
    assert "URUCHOM PRODUKCJĘ" not in response.text
    assert "ZAPISZ SCENĘ" not in response.text
    assert 'src="/media/' in response.text


def test_top5_never_submits_narration(studio):
    import json

    client, state, _ = studio
    state["format"] = "top5"
    response = client.get(f"/videos/{VIDEO}")
    assert 'name="narration"' not in response.text
    response = client.post(
        f"/videos/{VIDEO}/scenes/{SCENE}/edit",
        data={
            "csrf": client.cookies[CSRF],
            "narration": "forged",
            "visual_prompt": "New image",
            "mood": "happy",
            "caption_emphasis": "One\nTwo",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    data = json.loads(state["calls"][-1].content)
    assert "narration" not in data
    assert data["caption_emphasis"] == ["One", "Two"]


def test_scene_error_retains_input_and_wrong_scene_cannot_mutate(studio):
    client, state, _ = studio
    client.get(f"/videos/{VIDEO}")
    state["error"] = 409
    data = {"csrf": client.cookies[CSRF], "narration": "Moja nowa narracja", "visual_prompt": "Las"}
    response = client.post(f"/videos/{VIDEO}/scenes/{SCENE}/edit", data=data)
    assert response.status_code == 409
    assert "Moja nowa narracja" in response.text
    assert "private detail" not in response.text
    count = len([r for r in state["calls"] if r.method == "PATCH"])
    assert client.post(f"/videos/{VIDEO}/scenes/{uuid4()}/edit", data=data).status_code == 404
    assert len([r for r in state["calls"] if r.method == "PATCH"]) == count


@pytest.mark.parametrize("path", [f"/ideas/{IDEA}/create-video", f"/videos/{VIDEO}/produce"])
def test_csrf_blocks_mutation(studio, path):
    client, state, _ = studio
    assert client.post(path).status_code == 403
    assert not state["calls"]


@pytest.mark.parametrize(
    "range_header,code,content",
    [(None, 200, b"0123456789"), ("bytes=2-5", 206, b"2345"), ("bytes=99-100", 416, None)],
)
def test_media_range_and_cleanup(studio, range_header, code, content):
    client, _, directory = studio
    response = client.get(
        f"/media/{ASSET}", headers={"Range": range_header} if range_header else {}
    )
    assert response.status_code == code
    if content is not None:
        assert response.content == content
    assert list(directory.iterdir()) == []
    assert response.headers["cache-control"] == "no-store"


def test_media_auth_errors_and_unsafe_mime(studio):
    client, state, _ = studio
    state["error"] = 404
    response = client.get(f"/media/{ASSET}")
    assert response.status_code == 404
    assert "secret backend" not in response.text
    state["error"] = None
    state["mime"] = "text/html"
    response = client.get(f"/media/{ASSET}")
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")
    client.cookies.clear()
    before = len(state["calls"])
    assert client.get(f"/media/{ASSET}").status_code == 401
    assert len(state["calls"]) == before


def test_oversize_media_is_cleaned(studio, monkeypatch):
    client, _, directory = studio
    monkeypatch.setattr(get_settings(), "media_max_bytes", 5)
    assert client.get(f"/media/{ASSET}").status_code == 413
    assert not list(Path(directory).iterdir())


def test_production_and_regeneration_use_api_and_idempotency(studio):
    import json
    import re

    client, state, _ = studio
    page = client.get(f"/videos/{VIDEO}")
    key = re.search(r'name="key" value="([^"]+)"', page.text)[1]
    data = {"csrf": client.cookies[CSRF], "key": key}
    response = client.post(f"/videos/{VIDEO}/produce", data=data, follow_redirects=False)
    assert response.status_code == 303
    assert state["calls"][-1].url.path == f"/api/v1/videos/{VIDEO}/produce"
    response = client.post(
        f"/videos/{VIDEO}/scenes/{SCENE}/regenerate",
        data=data | {"kind": "image"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert state["calls"][-1].headers["idempotency-key"] == key
    assert json.loads(state["calls"][-1].content) == {"kind": "image"}


def test_status_endpoint_does_not_expose_task_results(studio):
    client, _, _ = studio
    response = client.get(f"/video-status/{VIDEO}")
    assert response.status_code == 200
    assert "result" not in response.json()["tasks"][0]
    client.cookies.clear()
    assert client.get(f"/video-status/{VIDEO}").status_code == 401
