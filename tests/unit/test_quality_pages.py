from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import SESSION, app

V, T, R, A = (str(uuid4()) for _ in range(4))


@pytest.fixture
def studio():
    state = {"code": 200, "calls": [], "reports": []}

    def handle(request):
        state["calls"].append(request)
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer synthetic"
        if request.url.path.endswith("/me"):
            data = dict(email="test@example.com", role="user")
        elif request.url.path.endswith("/quality-checks"):
            return httpx.Response(state["code"], json=state["reports"])
        else:
            data = dict(
                id=V,
                title="Film",
                status="READY",
                format="story",
                language="pl",
                duration_target=45,
                budget_limit_usd="1",
            )
        return httpx.Response(200, json=data)

    with TestClient(app) as client:
        http = httpx.AsyncClient(
            base_url="http://backend.test", transport=httpx.MockTransport(handle)
        )
        app.state.backend = BackendClient(http)
        client.cookies.set(SESSION, "synthetic", domain="testserver.local", path="/")
        yield client, state
        client.portal.call(http.aclose)


def test_empty_and_pending(studio):
    client, state = studio
    assert "Brak raportów kontroli jakości" in client.get(f"/videos/{V}/quality").text
    state["reports"] = [
        dict(
            id=R,
            task_id=T,
            render_task_id=T,
            final_asset_id=None,
            attempt=1,
            status="checking",
            report_json={},
            created_at="2026-10-01T12:00:00Z",
            completed_at=None,
        )
    ]
    response = client.get(f"/videos/{V}/quality")
    assert response.status_code == 200 and "Brak szczegółowych wyników" in response.text
    assert "Pobierz sprawdzony plik" not in response.text


def test_results_escaping_and_exact_asset(studio):
    client, state = studio
    state["reports"] = [
        dict(
            id=R,
            task_id=T,
            render_task_id=T,
            final_asset_id=A,
            attempt=2,
            status="passed",
            created_at="2026-10-01T12:00:00Z",
            completed_at="2026-10-01T12:01:00Z",
            report_json=dict(
                duration_seconds=0,
                target_seconds=45,
                visual_provider="mock",
                checks=[
                    dict(code="<script>bad</script>", outcome="skipped"),
                    dict(code="future_check", outcome="future"),
                    dict(code="duration", outcome="failed"),
                ],
            ),
        )
    ]
    response = client.get(f"/videos/{V}/quality")
    assert response.status_code == 200
    for value in [
        "Pominięta",
        "Niezaliczona",
        "future",
        "&lt;script&gt;",
        "0.0 s",
        f"/media/{A}?attachment=true",
        f"/tasks/{T}",
    ]:
        assert value in response.text
    assert "Wynik starszej kontroli" in response.text


@pytest.mark.parametrize("code", [401, 403, 404, 503])
def test_errors(studio, code):
    client, state = studio
    state["code"] = code
    response = client.get(f"/videos/{V}/quality", follow_redirects=False)
    assert response.status_code == (303 if code == 401 else code)


def test_invalid_and_anonymous(studio):
    client, state = studio
    state["reports"] = [{}]
    assert client.get(f"/videos/{V}/quality").status_code == 503
    client.cookies.clear()
    state["calls"].clear()
    assert (
        client.get(f"/videos/{V}/quality", follow_redirects=False).headers["location"] == "/login"
    )
    assert not state["calls"]
