from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, PlainTextResponse

from app.api.client import BackendError
from app.api.media import download
from app.config import get_settings
from app.pages.channels import SESSION

router = APIRouter()
SAFE_MEDIA = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
}


class PrivateFile(FileResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Includes rejected Range headers and client disconnects.
            self.path.unlink(missing_ok=True)


@router.get("/media/{asset_id}")
async def media(request: Request, asset_id: UUID, attachment: bool = False):
    token = request.cookies.get(SESSION)
    if not token:
        return PlainTextResponse("Zaloguj się, aby otworzyć zasób.", status_code=401)
    try:
        path, mime = await download(
            request.app.state.backend, asset_id, token, get_settings().media_max_bytes
        )
        safe = mime in SAFE_MEDIA
        return PrivateFile(
            path,
            media_type=mime if safe else "application/octet-stream",
            filename=f"{asset_id}{SAFE_MEDIA.get(mime, '.bin')}",
            content_disposition_type="attachment" if attachment or not safe else "inline",
            headers={"Cache-Control": "no-store"},
        )
    except BackendError as exc:
        status = exc.status if exc.status in (401, 403, 404, 409, 413) else 503
        return PlainTextResponse(
            "Nie można pobrać zasobu. Sprawdź sesję i dostępność pliku.", status_code=status
        )
