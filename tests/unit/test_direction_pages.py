from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import SESSION, app

V, P, S = (str(uuid4()) for _ in range(3))


@pytest.fixture
def studio():
    state = dict(
        code=200,
        video_code=200,
        calls=[],
        plan=dict(
            id=P,
            video_id=V,
            visual_budget_usd="0.500001",
            estimated_cost_usd="0.240001",
            requested_video_ratio=0.5,
            pricing_snapshot=dict(image_usd="0.01", video_second_usd="0.02"),
            created_at="2026-10-01T12:00:00Z",
            scenes=[
                dict(
                    id=S,
                    position=2,
                    duration="5.5",
                    visual_prompt="<script>bad</script>",
                    visual_type="image",
                    camera_motion="static",
                    visual_style="Styl",
                    importance=0.9,
                    generation_priority=1,
                )
            ],
        ),
    )

    def handle(request):
        state["calls"].append(request)
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer synthetic"
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=dict(email="test@example.com", role="user"))
        if request.url.path.endswith("/direction"):
            return httpx.Response(state["code"], json=state["plan"])
        return httpx.Response(
            state["video_code"],
            json=dict(
                id=V,
                title="Film",
                status="READY",
                format="story",
                language="pl",
                duration_target=45,
                budget_limit_usd="1",
            ),
        )

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "synthetic", domain="testserver.local", path="/")
        yield client, state
        client.portal.call(http.aclose)


def test_plan_and_precision(studio):
    client, state = studio
    response = client.get(f"/videos/{V}/direction")
    assert response.status_code == 200
    for value in [
        "0.500001 USD",
        "0.240001 USD",
        "Scena 2",
        "Priorytet generowania: 1",
        "&lt;script&gt;bad",
        f"#scene-{S}",
        "nie rozliczenie całej produkcji",
    ]:
        assert value in response.text
    assert len(state["calls"]) == 3


def test_unknown_presentation_values(studio):
    client, state = studio
    state["plan"]["scenes"][0].update(visual_type="future_type", camera_motion="future_motion")
    response = client.get(f"/videos/{V}/direction")
    assert "future_type" in response.text and "future_motion" in response.text


def test_missing_plan_vs_missing_video(studio):
    client, state = studio
    state["code"] = 404
    response = client.get(f"/videos/{V}/direction")
    assert response.status_code == 200 and "Brak planu wizualnego" in response.text
    state["video_code"] = 404
    response = client.get(f"/videos/{V}/direction")
    assert response.status_code == 404 and "Brak planu wizualnego" not in response.text


@pytest.mark.parametrize("code", [401, 403, 503])
def test_errors(studio, code):
    client, state = studio
    state["code"] = code
    assert client.get(f"/videos/{V}/direction", follow_redirects=False).status_code == (
        303 if code == 401 else code
    )


def test_wrong_response_and_anonymous(studio):
    client, state = studio
    state["plan"]["video_id"] = str(uuid4())
    assert client.get(f"/videos/{V}/direction").status_code == 503
    state["plan"] = {}
    assert client.get(f"/videos/{V}/direction").status_code == 503
    client.cookies.clear()
    state["calls"].clear()
    assert (
        client.get(f"/videos/{V}/direction", follow_redirects=False).headers["location"] == "/login"
    )
    assert not state["calls"]
