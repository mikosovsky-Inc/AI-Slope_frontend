"""Channel forms delegate validation and workflow to the backend HTTP API."""

import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.client import BackendError
from app.api.panel import User, read
from app.config import get_settings

router = APIRouter()
SESSION = "ai_slop_session"
CSRF = "ai_slop_csrf"


def login():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION)
    return response


async def options(backend):
    schema = await backend.request("GET", "/openapi.json", api=False)
    try:
        models = schema["components"]["schemas"]
        fields = models["ChannelCreate"]["properties"]
        return {"languages": fields["language"]["enum"], "modes": models["AutopilotMode"]["enum"]}
    except (KeyError, TypeError):
        raise BackendError(502) from None


def page(request, *, status=200, **context):
    csrf = request.cookies.get(CSRF) or secrets.token_urlsafe(32)
    response = request.app.state.templates.TemplateResponse(
        request=request,
        name="channel.html",
        context={
            "section": "channels",
            "csrf": csrf,
            "message": "",
            "user": None,
            "channel": None,
            "values": {},
            "choices": None,
            "task": None,
            "key": str(uuid4()),
            "creating": False,
            **context,
        },
        status_code=status,
    )
    response.set_cookie(
        CSRF, csrf, httponly=True, samesite="lax", secure=get_settings().cookie_secure
    )
    return response


def error_message(status):
    return {
        403: "Nie masz dostępu do tego kanału.",
        404: "Nie znaleziono kanału lub zadania.",
        409: "Kanał zmienił się podczas operacji. Odśwież dane i spróbuj ponownie.",
        422: (
            "Sprawdź pola: opis 10–4000 znaków, nazwa do 120, 1–24 filmy dziennie, "
            "budżet ponad 0 do 100 USD (do 4 miejsc po przecinku)."
        ),
        429: "Zbyt wiele żądań. Poczekaj chwilę.",
    }.get(
        status,
        "Nie udało się potwierdzić wyniku operacji. Sprawdź kanały przed ponownym wysłaniem.",
    )


@router.get("/channels/new")
async def new(request: Request):
    token = request.cookies.get(SESSION)
    if not token:
        return login()
    try:
        backend = request.app.state.backend
        user = await read(backend, "/auth/me", token, User)
        return page(
            request,
            creating=True,
            user=user,
            choices=await options(backend),
            values={
                "language": "pl",
                "videos_per_day": 2,
                "budget_per_video_usd": "0.20",
                "autopilot_mode": "manual",
            },
        )
    except BackendError as exc:
        return (
            login()
            if exc.status == 401
            else page(request, status=503, creating=True, message=error_message(exc.status))
        )


@router.get("/channels/{channel_id}")
async def detail(request: Request, channel_id: UUID, task_id: UUID | None = None):
    token = request.cookies.get(SESSION)
    if not token:
        return login()
    try:
        backend = request.app.state.backend
        user = await read(backend, "/auth/me", token, User)
        task = None
        if task_id:
            task = await backend.request("GET", f"/tasks/{task_id}", token=token)
        # Read the strategy after task status to avoid showing stale data with success.
        channel = await backend.request("GET", f"/channels/{channel_id}", token=token)
        return page(
            request,
            user=user,
            channel=channel,
            values=channel,
            choices=await options(backend),
            task=task,
        )
    except BackendError as exc:
        return (
            login()
            if exc.status == 401
            else page(
                request,
                status=exc.status if exc.status in (403, 404) else 503,
                message=error_message(exc.status),
            )
        )


@router.post("/channels/new")
@router.post("/channels/{channel_id}/settings")
@router.post("/channels/{channel_id}/analyze")
@router.post("/channels/{channel_id}/activate")
@router.post("/channels/{channel_id}/pause")
async def save(request: Request, channel_id: UUID | None = None):
    token = request.cookies.get(SESSION)
    if not token:
        return login()
    form = await request.form(max_fields=20, max_files=0)
    supplied, expected = form.get("csrf", ""), request.cookies.get(CSRF, "")
    if (
        not isinstance(supplied, str)
        or not expected
        or not secrets.compare_digest(supplied.encode(), expected.encode())
    ):
        return page(request, status=403, message="Formularz wygasł. Odśwież stronę.")
    backend = request.app.state.backend
    creating = channel_id is None
    action = request.url.path.rsplit("/", 1)[-1]
    fields = (
        "name",
        "idea",
        "language",
        "videos_per_day",
        "budget_per_video_usd",
        "autopilot_mode",
    )
    values = {k: form.get(k, "") for k in fields}
    context = {"creating": creating, "values": values}
    try:
        context["user"] = await read(backend, "/auth/me", token, User)
        if not creating:
            context["channel"] = await backend.request(
                "GET", f"/channels/{channel_id}", token=token
            )
        if action in ("new", "settings"):
            context["choices"] = await options(backend)
            if not all(isinstance(v, str) for v in values.values()):
                raise BackendError(422)
            data = values.copy()
            try:
                data["videos_per_day"] = int(data["videos_per_day"])
            except ValueError:
                raise BackendError(422) from None
            if creating and not data["name"].strip():
                del data["name"]
            result = await backend.request(
                "POST" if creating else "PATCH",
                "/channels" if creating else f"/channels/{channel_id}",
                token=token,
                data=data,
            )
            channel_id = UUID(result["id"])
        elif action == "analyze":
            key = form.get("key", "")
            try:
                key = str(UUID(str(key)))
            except ValueError:
                raise BackendError(422) from None
            context["key"] = key
            result = await backend.request(
                "POST", f"/channels/{channel_id}/analyze", token=token, key=key
            )
            if "kind" in result:
                task_id = UUID(result["id"])
                return RedirectResponse(
                    f"/channels/{channel_id}?task_id={task_id}", status_code=303
                )
        else:
            await backend.request("POST", f"/channels/{channel_id}/{action}", token=token)
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)
    except BackendError as exc:
        if exc.status == 401:
            return login()
        return page(
            request,
            status=exc.status if exc.status in (403, 404, 409, 422, 429) else 503,
            message=error_message(exc.status),
            **context,
        )


@router.get("/task-status/{task_id}")
async def task_status(request: Request, task_id: UUID):
    token = request.cookies.get(SESSION)
    if not token:
        return JSONResponse({"message": "Sesja wygasła. Zaloguj się ponownie."}, status_code=401)
    try:
        result = await request.app.state.backend.request("GET", f"/tasks/{task_id}", token=token)
        return {"status": result["status"]}
    except BackendError as exc:
        return JSONResponse(
            {"message": "Nie można odczytać stanu zadania. Odśwież stronę."}, status_code=exc.status
        )
