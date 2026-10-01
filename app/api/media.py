"""Authenticated backend downloads; private temporary files, never public assets."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

import anyio
import httpx

from app.api.client import BackendError


async def download(backend, asset_id: UUID, token: str, max_bytes: int):
    path = None
    try:
        async with backend.http.stream(
            "GET",
            f"/api/v1/assets/{asset_id}/download",
            headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "identity"},
            timeout=httpx.Timeout(120, connect=10),
        ) as response:
            if not response.is_success:
                raise BackendError(response.status_code)
            mime = response.headers.get("content-type", "application/octet-stream").split(";")[0]
            with NamedTemporaryFile(prefix="ai-slop-preview-", delete=False) as file:
                path = Path(file.name)
            total = 0
            async with await anyio.open_file(path, "wb") as file:
                async for chunk in response.aiter_bytes(64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise BackendError(413)
                    await file.write(chunk)
        return path, mime
    except BaseException as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        if isinstance(exc, httpx.RequestError):
            raise BackendError(503) from None
        raise
