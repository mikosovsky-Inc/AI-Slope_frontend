import secrets
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.api.client import BackendClient, BackendError
from app.api.panel import ChannelPage, Dashboard, User, read

ROOT = Path(__file__).resolve().parent
SESSION = "ai_slop_session"
CSRF = "ai_slop_csrf"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    api_base_url: AnyHttpUrl = "http://localhost:8000"
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(
        base_url=str(get_settings().api_base_url), timeout=15, follow_redirects=False
    ) as http:
        app.state.backend = BackendClient(http)
        yield


app = FastAPI(
    title="AI-Slop Frontend", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
)
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")
templates = Jinja2Templates(directory=ROOT / "templates")


def cookie(response, name, value, max_age=None):
    response.set_cookie(
        name,
        value,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def render(request, *, mode="login", user=None, first=False, message="", status=200):
    csrf = secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "mode": mode,
            "user": user,
            "first": first,
            "message": message,
            "csrf": csrf,
        },
        status_code=status,
    )
    cookie(response, CSRF, csrf)
    return response


@app.middleware("http")
async def private_pages(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    return response


@app.get("/")
@app.get("/login")
@app.get("/register")
async def index(request: Request):
    backend = request.app.state.backend
    try:
        token = request.cookies.get(SESSION)
        if token:
            try:
                await backend.request("GET", "/auth/me", token=token)
                return RedirectResponse("/app", status_code=303)
            except BackendError as exc:
                if exc.status != 401:
                    raise
        setup = await backend.request("GET", "/auth/setup")
        first = setup["registration_required"]
        mode = "register" if first or request.url.path == "/register" else "login"
        response = render(request, mode=mode, first=first)
        if token:
            response.delete_cookie(SESSION, path="/")
        return response
    except BackendError:
        return render(
            request,
            mode="unavailable",
            status=503,
            message="Studio jest chwilowo niedostępne. Spróbuj ponownie.",
        )


def session_redirect():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION, path="/")
    return response


@app.get("/app")
@app.get("/channels")
async def studio(request: Request, offset: int = Query(default=0, ge=0)):
    token = request.cookies.get(SESSION)
    if not token:
        return session_redirect()
    section = "channels" if request.url.path == "/channels" else "dashboard"
    backend = request.app.state.backend
    user = None
    data = None
    message = ""
    status = 200
    try:
        user = await read(backend, "/auth/me", token, User)
        if section == "channels":
            data = await read(
                backend, "/channels", token, ChannelPage, params={"limit": 12, "offset": offset}
            )
        else:
            data = await read(backend, "/dashboard", token, Dashboard)
    except BackendError as exc:
        if exc.status == 401:
            return session_redirect()
        status = 403 if exc.status == 403 else 503
        message = (
            "Nie masz dostępu do tego widoku."
            if status == 403
            else "Nie udało się pobrać danych studia. Spróbuj ponownie."
        )
    csrf = secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request,
        name="studio.html",
        context={
            "section": section,
            "user": user,
            "data": data,
            "message": message,
            "csrf": csrf,
            "offset": offset,
        },
        status_code=status,
    )
    cookie(response, CSRF, csrf)
    return response


@app.post("/login")
@app.post("/register")
@app.post("/logout")
async def submit(request: Request):
    form = await request.form(max_fields=10, max_files=0)
    supplied = form.get("csrf", "")
    expected = request.cookies.get(CSRF, "")
    if (
        not isinstance(supplied, str)
        or not expected
        or not secrets.compare_digest(supplied.encode(), expected.encode())
    ):
        return render(request, message="Formularz wygasł. Spróbuj ponownie.", status=403)
    mode = request.url.path[1:]
    if mode == "logout":
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION, path="/")
        response.delete_cookie(CSRF, path="/")
        return response
    email, password = form.get("email", ""), form.get("password", "")
    if not isinstance(email, str) or not isinstance(password, str):
        return render(request, mode=mode, message="Sprawdź dane formularza.", status=422)
    if mode == "register" and password != form.get("confirm_password"):
        return render(request, mode=mode, message="Hasła nie są takie same.", status=422)
    try:
        result = await request.app.state.backend.request(
            "POST", f"/auth/{mode}", data={"email": email.strip(), "password": password}
        )
    except BackendError as exc:
        messages = {
            401: "Nieprawidłowy e-mail lub hasło.",
            409: "Ten e-mail ma już konto. Przejdź do logowania.",
            422: "Sprawdź e-mail i hasło. Nowe hasło musi mieć 12–128 znaków.",
            429: "Zbyt wiele prób. Poczekaj chwilę i spróbuj ponownie.",
        }
        return render(
            request,
            mode=mode,
            status=exc.status if exc.status in messages else 503,
            message=messages.get(exc.status, "Studio jest chwilowo niedostępne."),
        )
    if mode == "register":
        return render(request, message="Konto utworzone. Możesz się zalogować.")
    response = RedirectResponse("/app", status_code=303)
    cookie(response, SESSION, result["access_token"], max_age=result["expires_in"])
    return response


@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
def apple_touch_icon():
    return FileResponse(ROOT / "assets/icons/apple-touch-icon.png", media_type="image/png")
