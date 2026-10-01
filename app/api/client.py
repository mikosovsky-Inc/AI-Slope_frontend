"""HTTP boundary: no backend imports or domain decisions."""

import httpx


class BackendError(Exception):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Backend request failed ({status})")


class BackendClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def request(
        self, method: str, path: str, *, token=None, data=None, params=None, key=None, api=True
    ):
        try:
            response = await self.http.request(
                method,
                ("/api/v1" if api else "") + path,
                json=data,
                params=params,
                headers=({"Authorization": f"Bearer {token}"} if token else {})
                | ({"Idempotency-Key": key} if key else {}),
            )
        except httpx.RequestError:
            raise BackendError(503) from None
        if not response.is_success:
            raise BackendError(response.status_code)
        try:
            return response.json()
        except ValueError:
            raise BackendError(502) from None
