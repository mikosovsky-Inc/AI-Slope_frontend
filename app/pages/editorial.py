"""Competitor benchmarks and idea review through the backend API only."""

import secrets
from urllib.parse import urlencode
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.api.client import BackendError
from app.api.editorial import Competitors, Ideas
from app.api.panel import User, read
from app.config import get_settings
from app.pages.channels import CSRF, SESSION, login

router = APIRouter()


def render(request, status=200, **context):
    csrf = request.cookies.get(CSRF) or secrets.token_urlsafe(32)
    response = request.app.state.templates.TemplateResponse(
        request=request,
        name="editorial.html",
        context={
            "section": "channels",
            "user": None,
            "channel": None,
            "data": None,
            "task": None,
            "message": "",
            "statuses": [],
            "selected": "",
            "offset": 0,
            "count": 10,
            "csrf": csrf,
            "key": str(uuid4()),
            **context,
        },
        status_code=status,
    )
    response.set_cookie(
        CSRF, csrf, httponly=True, samesite="lax", secure=get_settings().cookie_secure
    )
    return response


def failure(request, exc, **context):
    if exc.status == 401:
        return login()
    status = exc.status if exc.status in (403, 404, 409, 422, 429) else 503
    message = {
        403: "Nie masz dostępu do tej operacji.",
        404: "Nie znaleziono kanału, pomysłu lub zadania.",
        409: (
            "Operacja jest niedostępna w aktualnym stanie. "
            "Sprawdź strategię kanału i status pomysłu."
        ),
        422: "Sprawdź formularz. Liczba pomysłów musi wynosić od 10 do 20.",
        429: "Zbyt wiele żądań. Poczekaj chwilę i spróbuj ponownie.",
    }.get(status, "Nie udało się pobrać danych lub potwierdzić operacji. Odśwież widok.")
    return render(request, status=status, message=message, **context)


async def load(request, channel_id, view, *, offset=0, selected="", task_id=None):
    backend = request.app.state.backend
    token = request.cookies[SESSION]
    user = await read(backend, "/auth/me", token, User)
    # Observe terminal status before retrieving the data produced by that task.
    task = await backend.request("GET", f"/tasks/{task_id}", token=token) if task_id else None
    channel = await backend.request("GET", f"/channels/{channel_id}", token=token)
    statuses = []
    if view == "ideas":
        schema = await backend.request("GET", "/openapi.json", api=False)
        try:
            statuses = schema["components"]["schemas"]["IdeaStatus"]["enum"]
        except (KeyError, TypeError):
            raise BackendError(502) from None
    params = {"limit": 10, "offset": offset}
    if selected and view == "ideas":
        params["status"] = selected
    data = await read(
        backend,
        f"/channels/{channel_id}/{view}",
        token,
        Ideas if view == "ideas" else Competitors,
        params=params,
    )
    query = {"status": selected} if selected else {}
    if task_id:
        query["task_id"] = str(task_id)
    return {
        "user": user,
        "channel": channel,
        "task": task,
        "data": data,
        "statuses": statuses,
        "selected": selected,
        "offset": offset,
        "previous": "?" + urlencode(query | {"offset": max(0, offset - data.limit)}),
        "next": "?" + urlencode(query | {"offset": offset + data.limit}),
    }


@router.get("/channels/{channel_id}/competitors")
@router.get("/channels/{channel_id}/ideas")
async def listing(
    request: Request,
    channel_id: UUID,
    offset: int = Query(0, ge=0),
    status: str = "",
    task_id: UUID | None = None,
):
    view = request.url.path.rsplit("/", 1)[-1]
    if not request.cookies.get(SESSION):
        return login()
    try:
        context = await load(
            request, channel_id, view, offset=offset, selected=status, task_id=task_id
        )
        return render(request, view=view, channel_id=channel_id, **context)
    except BackendError as exc:
        return failure(request, exc, view=view, channel_id=channel_id)


async def checked_form(request):
    form = await request.form(max_fields=10, max_files=0)
    supplied, expected = form.get("csrf", ""), request.cookies.get(CSRF, "")
    if (
        not isinstance(supplied, str)
        or not expected
        or not secrets.compare_digest(supplied.encode(), expected.encode())
    ):
        raise BackendError(403)
    return form


@router.post("/channels/{channel_id}/competitors/research")
@router.post("/channels/{channel_id}/ideas/generate")
async def generate(request: Request, channel_id: UUID):
    view = "ideas" if request.url.path.endswith("/generate") else "competitors"
    if not request.cookies.get(SESSION):
        return login()
    context = {"view": view, "channel_id": channel_id}
    try:
        form = await checked_form(request)
        context.update(await load(request, channel_id, view))
        try:
            key = str(UUID(str(form.get("key", ""))))
            context["key"] = key
            count = int(str(form.get("count", "10")))
            context["count"] = count
        except ValueError:
            raise BackendError(422) from None
        path = "ideas/generate" if view == "ideas" else "competitor-research"
        result = await request.app.state.backend.request(
            "POST",
            f"/channels/{channel_id}/{path}",
            token=request.cookies[SESSION],
            key=key,
            params={"count": count} if view == "ideas" else None,
        )
        location = f"/channels/{channel_id}/{view}"
        if "kind" in result:
            location += "?" + urlencode({"task_id": str(UUID(result["id"]))})
        return RedirectResponse(location, status_code=303)
    except BackendError as exc:
        return failure(request, exc, **context)


@router.post("/ideas/{idea_id}/approve")
@router.post("/ideas/{idea_id}/reject")
async def decide(request: Request, idea_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    channel_id = None
    try:
        form = await checked_form(request)
        try:
            channel_id = UUID(str(form.get("channel_id", "")))
            offset = max(0, int(str(form.get("offset", "0"))))
        except ValueError:
            raise BackendError(422) from None
        selected = str(form.get("status", ""))
        action = request.url.path.rsplit("/", 1)[-1]
        result = await request.app.state.backend.request(
            "POST", f"/ideas/{idea_id}/{action}", token=request.cookies[SESSION]
        )
        # Destination comes from the backend, not the submitted channel id.
        channel_id = UUID(result["channel_id"])
        return RedirectResponse(
            f"/channels/{channel_id}/ideas?" + urlencode({"offset": offset, "status": selected}),
            status_code=303,
        )
    except BackendError as exc:
        return failure(request, exc, view="ideas", channel_id=channel_id)
