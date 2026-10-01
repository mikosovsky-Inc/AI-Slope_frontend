import secrets
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.api.client import BackendError
from app.api.operations import Budget, CostPage, Jobs, Recoveries, Revisions, TaskDetail
from app.api.panel import User, read
from app.api.videos import Assets, Video
from app.config import get_settings
from app.pages.channels import CSRF, SESSION, login
from app.pages.editorial import checked_form

router = APIRouter()


def page(request, status_code=200, **context):
    csrf = request.cookies.get(CSRF) or secrets.token_urlsafe(32)
    response = request.app.state.templates.TemplateResponse(
        request=request,
        name="operations.html",
        context={
            "section": "channels",
            "user": None,
            "message": "",
            "data": None,
            "video": None,
            "channel": None,
            "task": None,
            "revisions": [],
            "history": [],
            "choices": {},
            "assets": [],
            "values": {},
            "csrf": csrf,
            **context,
        },
        status_code=status_code,
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
        403: "Brak uprawnień lub formularz wygasł. Odśwież stronę.",
        404: "Nie znaleziono danych. Sprawdź, czy należą do Twojego konta.",
        409: (
            "Backend odrzucił operację w obecnym stanie. "
            "Sprawdź zadania, wersję filmu i wymagane dane odzyskiwania."
        ),
        422: "Sprawdź pola formularza i wymagane potwierdzenia.",
        429: "Zbyt wiele operacji. Poczekaj chwilę.",
    }.get(status, "Nie można potwierdzić wyniku operacji. Odśwież dane przed ponowieniem.")
    return page(request, status_code=status, message=message, **context)


async def schema_choices(backend):
    schema = await backend.request("GET", "/openapi.json", api=False)
    try:
        models = schema["components"]["schemas"]
        motion = models["RevisionPatch"]["properties"]["camera_motion"]
        return {
            "statuses": models["TaskStatus"]["enum"],
            "kinds": models["TaskKind"]["enum"],
            "recovery": models["RecoveryInput"]["properties"]["action"]["enum"],
            "motions": next(v["enum"] for v in motion["anyOf"] if "enum" in v),
        }
    except (KeyError, TypeError, StopIteration):
        raise BackendError(502) from None


@router.get("/channels/{channel_id}/costs")
async def costs(request: Request, channel_id: UUID, offset: int = Query(0, ge=0)):
    if not request.cookies.get(SESSION):
        return login()
    try:
        backend, token = request.app.state.backend, request.cookies[SESSION]
        user = await read(backend, "/auth/me", token, User)
        channel = await backend.request("GET", f"/channels/{channel_id}", token=token)
        data = await read(
            backend,
            f"/channels/{channel_id}/costs",
            token,
            CostPage,
            params={"limit": 20, "offset": offset},
        )
        return page(
            request,
            view="costs",
            user=user,
            channel=channel,
            data=data,
            offset=offset,
            previous=f"?offset={max(0, offset - 20)}",
            next=f"?offset={offset + 20}",
        )
    except BackendError as exc:
        return failure(request, exc, view="costs")


@router.get("/videos/{video_id}/budget")
async def budget(request: Request, video_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    try:
        backend, token = request.app.state.backend, request.cookies[SESSION]
        user = await read(backend, "/auth/me", token, User)
        video = await read(backend, f"/videos/{video_id}", token, Video)
        data = await read(backend, f"/videos/{video_id}/budget", token, Budget)
        return page(request, view="budget", user=user, video=video, data=data)
    except BackendError as exc:
        return failure(request, exc, view="budget")


@router.get("/jobs")
async def jobs(
    request: Request,
    status: str = "",
    kind: str = "",
    video_id: str = "",
    offset: int = Query(0, ge=0),
):
    if not request.cookies.get(SESSION):
        return login()
    try:
        backend, token = request.app.state.backend, request.cookies[SESSION]
        user = await read(backend, "/auth/me", token, User)
        if user.role != "admin":
            raise BackendError(403)
        filters = {
            k: v
            for k, v in {
                "status": status,
                "kind": kind,
                "video_id": str(video_id) if video_id else "",
            }.items()
            if v
        }
        data = await read(
            backend, "/admin/jobs", token, Jobs, params=filters | {"limit": 20, "offset": offset}
        )
        return page(
            request,
            view="jobs",
            section="jobs",
            user=user,
            data=data,
            choices=await schema_choices(backend),
            values=filters,
            offset=offset,
            previous="?" + urlencode(filters | {"offset": max(0, offset - 20)}),
            next="?" + urlencode(filters | {"offset": offset + 20}),
        )
    except BackendError as exc:
        return failure(request, exc, view="jobs", section="jobs")


async def task_context(request, task_id):
    backend, token = request.app.state.backend, request.cookies[SESSION]
    user = await read(backend, "/auth/me", token, User)
    task = await read(backend, f"/tasks/{task_id}", token, TaskDetail)
    history = await read(backend, f"/tasks/{task_id}/recoveries", token, Recoveries)
    assets = (
        await read(backend, f"/videos/{task.video_id}/assets", token, Assets)
        if task.video_id
        else None
    )
    return {
        "user": user,
        "task": task,
        "history": history.root,
        "assets": assets.root if assets else [],
        "choices": await schema_choices(backend),
    }


@router.get("/tasks/{task_id}")
async def task(request: Request, task_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    try:
        return page(request, view="task", **await task_context(request, task_id))
    except BackendError as exc:
        return failure(request, exc, view="task")


@router.post("/tasks/{task_id}/recover")
@router.post("/tasks/{task_id}/retry")
async def recover(request: Request, task_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    context = {"view": "task"}
    try:
        form = await checked_form(request)
        context.update(await task_context(request, task_id))
        task = context["task"]
        if not task.video_id:
            raise BackendError(409)
        if request.url.path.endswith("/retry"):
            path = f"/videos/{task.video_id}/retry"
            data = {"task_id": str(task_id)}
        else:
            values = {
                k: str(form.get(k, "")) for k in ("action", "note", "provider_job_id", "asset_id")
            }
            context["values"] = values
            data = {"action": values["action"], "note": values["note"]}
            if values["action"] == "abandon" and form.get("confirmed") != "yes":
                raise BackendError(422)
            for field in ("provider_job_id", "asset_id"):
                if values[field].strip():
                    data[field] = values[field].strip()
            path = f"/tasks/{task_id}/recover"
        await request.app.state.backend.request(
            "POST", path, token=request.cookies[SESSION], data=data
        )
        return RedirectResponse(f"/tasks/{task_id}", status_code=303)
    except BackendError as exc:
        return failure(request, exc, **context)


async def revision_context(request, video_id):
    backend, token = request.app.state.backend, request.cookies[SESSION]
    user = await read(backend, "/auth/me", token, User)
    revisions = await read(backend, f"/videos/{video_id}/revisions", token, Revisions)
    video = await read(backend, f"/videos/{video_id}", token, Video)
    return {
        "user": user,
        "video": video,
        "revisions": revisions.root,
        "choices": await schema_choices(backend),
    }


@router.get("/videos/{video_id}/revisions")
async def revisions(request: Request, video_id: UUID):
    if not request.cookies.get(SESSION):
        return login()
    try:
        return page(request, view="revisions", **await revision_context(request, video_id))
    except BackendError as exc:
        return failure(request, exc, view="revisions")


@router.post("/videos/{video_id}/revisions")
@router.post("/videos/{video_id}/revisions/{revision_id}/produce")
@router.post("/videos/{video_id}/revisions/{revision_id}/cancel")
@router.post("/videos/{video_id}/revisions/{revision_id}/scenes/{scene_id}")
async def change_revision(
    request: Request, video_id: UUID, revision_id: UUID | None = None, scene_id: UUID | None = None
):
    if not request.cookies.get(SESSION):
        return login()
    context = {"view": "revisions"}
    try:
        form = await checked_form(request)
        context.update(await revision_context(request, video_id))
        path = f"/videos/{video_id}/revisions"
        data = None
        method = "POST"
        if revision_id:
            revision = next((r for r in context["revisions"] if r.id == revision_id), None)
            if revision is None:
                raise BackendError(404)
            path += f"/{revision_id}"
            if scene_id:
                if not any(s.id == scene_id for s in revision.scenes):
                    raise BackendError(404)
                fields = ["visual_prompt", "camera_motion"]
                if context["video"].format != "top5":
                    fields.append("narration")
                data = {f: str(form.get(f, "")) for f in fields}
                context["values"] = {str(revision_id) + str(scene_id): data}
                path += f"/scenes/{scene_id}"
                method = "PATCH"
            else:
                action = request.url.path.rsplit("/", 1)[-1]
                if action == "cancel" and form.get("confirmed") != "yes":
                    raise BackendError(422)
                path += f"/{action}"
        await request.app.state.backend.request(
            method, path, token=request.cookies[SESSION], data=data
        )
        return RedirectResponse(f"/videos/{video_id}/revisions", status_code=303)
    except BackendError as exc:
        return failure(request, exc, **context)
