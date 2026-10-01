from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.client import BackendClient
from main import SESSION, app

V, D, F = (str(uuid4()) for _ in range(3))


@pytest.fixture
def studio():
    source = dict(source_url="https://example.com/source", source_title="Dokument testowy")
    fact = dict(id=F, document_id=D, statement="<script>bad</script>", confidence=0.9, **source)
    state = dict(
        calls=[],
        format="top5",
        script_code=200,
        research_code=200,
        research=dict(
            video_id=V,
            documents=[
                dict(id=D, content="Zapisany tekst", retrieved_at="2026-10-01T12:00:00Z", **source)
            ],
            facts=[fact],
        ),
        script=dict(video_id=V, citations=[dict(position=2, fact=fact)]),
    )

    def handle(request):
        state["calls"].append(request)
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer synthetic"
        if request.url.path.endswith("/me"):
            data = dict(email="test@example.com", role="user")
        elif request.url.path.endswith("/research"):
            return httpx.Response(state["research_code"], json=state["research"])
        elif request.url.path.endswith("/script"):
            return httpx.Response(state["script_code"], json=state["script"])
        else:
            data = dict(
                id=V,
                title="Film",
                status="SCRIPT_READY",
                format=state["format"],
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


def test_sources_and_citations(studio):
    client, _ = studio
    response = client.get(f"/videos/{V}/sources")
    assert response.status_code == 200
    for value in [
        "Scena 2",
        "&lt;script&gt;bad",
        "Zapisany tekst",
        "0.9",
        "heurystyką",
        "noopener noreferrer",
        f"#document-{D}",
    ]:
        assert value in response.text
    assert "<script>bad" not in response.text


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "data:text/html,bad", "https://user:secret@example.com"]
)
def test_unsafe_links_are_not_rendered(studio, url):
    client, state = studio
    for source in [
        *state["research"]["documents"],
        *state["research"]["facts"],
        state["script"]["citations"][0]["fact"],
    ]:
        source["source_url"] = url
    response = client.get(f"/videos/{V}/sources")
    assert response.status_code == 200
    assert url not in response.text
    assert "Zapisany tekst" in response.text


def test_missing_script_and_empty_corpus(studio):
    client, state = studio
    state["script_code"] = 404
    state["research"] = dict(video_id=V, documents=[], facts=[])
    response = client.get(f"/videos/{V}/sources")
    assert response.status_code == 200
    assert "Nie ma jeszcze zapisanego scenariusza" in response.text
    assert "Brak zapisanych faktów" in response.text


@pytest.mark.parametrize("code", [401, 403, 404, 503])
def test_research_failure_is_not_empty_state(studio, code):
    client, state = studio
    state["research_code"] = code
    response = client.get(f"/videos/{V}/sources", follow_redirects=False)
    assert response.status_code == (303 if code == 401 else code)
    assert "Brak zapisanych faktów" not in response.text


def test_script_failure_is_not_missing_script(studio):
    client, state = studio
    state["script_code"] = 503
    assert client.get(f"/videos/{V}/sources").status_code == 503


def test_wrong_video_response(studio):
    client, state = studio
    state["research"]["video_id"] = str(uuid4())
    assert client.get(f"/videos/{V}/sources").status_code == 503


def test_story_and_anonymous(studio):
    client, state = studio
    state["format"] = "story"
    assert "opowieścią fikcyjną" in client.get(f"/videos/{V}/sources").text
    assert len(state["calls"]) == 2
    client.cookies.clear()
    state["calls"].clear()
    assert (
        client.get(f"/videos/{V}/sources", follow_redirects=False).headers["location"] == "/login"
    )
    assert not state["calls"]
