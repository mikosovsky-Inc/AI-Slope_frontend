import json
import secrets
from urllib.parse import urlencode
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.client import BackendError
from app.api.panel import User, read
from app.api.videos import Assets, Scenes, Status, Video, Videos
from app.config import get_settings
from app.pages.channels import CSRF, SESSION, login
from app.pages.editorial import checked_form

router = APIRouter()


def render(request, status=200, **context):
    csrf = request.cookies.get(CSRF) or secrets.token_urlsafe(32)
    response = request.app.state.templates.TemplateResponse(
        request=request,
        name="videos.html",
        context={
            "section": "channels",
            "user": None,
            "video": None,
            "channel": None,
            "data": None,
            "message": "",
            "csrf": csrf,
            "key": str(uuid4()),
            "scenes": [],
            "assets": [],
            "state": None,
            "edited": {},
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
        403: "Nie masz dostępu lub formularz wygasł. Odśwież stronę.",
        404: "Nie znaleziono filmu, sceny lub zasobu.",
        409: "Backend nie pozwala na tę operację w obecnym stanie. Odśwież stan filmu.",
        422: "Sprawdź pola formularza. Narracja i opis obrazu: do 4000 znaków, nastrój: do 200.",
        429: "Zbyt wiele operacji. Poczekaj chwilę.",
    }.get(
        status,
        "Nie udało się odczytać danych lub potwierdzić operacji. Odśwież widok przed ponowieniem.",
    )
    return render(request, status=status, message=message, **context)


async def load(request, video_id):
    backend, token = request.app.state.backend, request.cookies[SESSION]
    user = await read(backend, "/auth/me", token, User)
    state = await read(backend, f"/videos/{video_id}/status", token, Status)
    video = await read(backend, f"/videos/{video_id}", token, Video)
    scenes = await read(backend, f"/videos/{video_id}/scenes", token, Scenes)
    assets = await read(backend, f"/videos/{video_id}/assets", token, Assets)
    return {
        "user": user,
        "state": state,
        "video": video,
        "scenes": scenes.root,
        "assets": assets.root,
        "poll_state": json.dumps(state.model_dump(mode="json")),
    }


@router.get("/channels/{channel_id}/videos")
async def listing(
    request: Request, channel_id: UUID, offset: int = Query(0, ge=0), status: str = ""
):
    if not request.cookies.get(SESSION):
        return login()
    try:
        backend, token = request.app.state.backend, request.cookies[SESSION]
        user = await read(backend, "/auth/me", token, User)
        channel = await backend.request("GET", f"/channels/{channel_id}", token=token)
        schema = await backend.request("GET", "/openapi.json", api=False)
        try:
            statuses = schema["components"]["schemas"]["VideoStatus"]["enum"]
        except (KeyError, TypeError):
            raise BackendError(502) from None
        params = {"limit": 10, "offset": offset} | ({"status": status} if status else {})
        data = await read(backend, f"/channels/{channel_id}/videos", token, Videos, params=params)
        return render(
            request,
            user=user,
            channel=channel,
            data=data,
            statuses=statuses,
            selected=status,
            offset=offset,
            previous="?" + urlencode({"status": status, "offset": max(0, offset - 10)}),
            next="?" + urlencode({"status": status, "offset": offset + 10}),
        )
    except BackendError as exc:
        return failure(request, exc)


@router.get("/videos/{video_id}")
async def detail(request: Request, video_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    try:
        return render(request, **await load(request, video_id))
    except BackendError as exc:
        return failure(request, exc)


@router.post("/ideas/{idea_id}/create-video")
async def create(request: Request, idea_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    try:
        await checked_form(request)
        result = await request.app.state.backend.request(
            "POST", f"/ideas/{idea_id}/create-video", token=request.cookies[SESSION]
        )
        return RedirectResponse(f"/videos/{UUID(result['id'])}", status_code=303)
    except BackendError as exc:
        return failure(request, exc)


@router.post("/videos/{video_id}/produce")
@router.post("/videos/{video_id}/script")
@router.post("/videos/{video_id}/research")
@router.post("/videos/{video_id}/top5-script")
async def produce(request: Request, video_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    context = {}
    try:
        form = await checked_form(request)
        context = await load(request, video_id)
        action = request.url.path.rsplit("/", 1)[-1]
        path = {"script": "script/generate", "top5-script": "top5-script/generate"}.get(
            action, action
        )
        try:
            key = str(UUID(str(form.get("key", ""))))
        except ValueError:
            raise BackendError(422) from None
        context["key"] = key
        await request.app.state.backend.request(
            "POST", f"/videos/{video_id}/{path}", token=request.cookies[SESSION], key=key
        )
        return RedirectResponse(f"/videos/{video_id}", status_code=303)
    except BackendError as exc:
        return failure(request, exc, **context)


@router.post("/videos/{video_id}/scenes/{scene_id}/edit")
@router.post("/videos/{video_id}/scenes/{scene_id}/regenerate")
async def scene_action(request: Request, video_id: UUID, scene_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    context = {}
    try:
        form = await checked_form(request)
        context = await load(request, video_id)
        if not any(s.id == scene_id for s in context["scenes"]):
            raise BackendError(404)
        if request.url.path.endswith("/edit"):
            fields = ["visual_prompt", "mood"]
            if context["video"].format != "top5":
                fields.append("narration")
            data = {f: form.get(f, "") for f in fields}
            emphasis = form.get("caption_emphasis", "")
            if not isinstance(emphasis, str) or not all(isinstance(v, str) for v in data.values()):
                raise BackendError(422)
            data["caption_emphasis"] = [s.strip() for s in emphasis.splitlines() if s.strip()]
            context["edited"] = {str(scene_id): data | {"caption_emphasis_text": emphasis}}
            await request.app.state.backend.request(
                "PATCH", f"/scenes/{scene_id}", token=request.cookies[SESSION], data=data
            )
        else:
            try:
                key = str(UUID(str(form.get("key", ""))))
            except ValueError:
                raise BackendError(422) from None
            context["key"] = key
            await request.app.state.backend.request(
                "POST",
                f"/scenes/{scene_id}/regenerate",
                token=request.cookies[SESSION],
                data={"kind": form.get("kind", "")},
                key=key,
            )
        return RedirectResponse(f"/videos/{video_id}#scene-{scene_id}", status_code=303)
    except BackendError as exc:
        return failure(request, exc, **context)


@router.get("/video-status/{video_id}")
async def poll(request: Request, video_id: UUID):
    if not request.cookies.get(SESSION):
        return JSONResponse({"message": "Sesja wygasła"}, status_code=401)
    try:
        state = await read(
            request.app.state.backend,
            f"/videos/{video_id}/status",
            request.cookies[SESSION],
            Status,
        )
        return state
    except BackendError as exc:
        return JSONResponse({"message": "Nie można odczytać stanu filmu"}, status_code=exc.status)
