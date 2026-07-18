import secrets

from fastapi import Header, HTTPException, Query, WebSocket, status

_token: str | None = None


def set_auth_token(token: str) -> None:
    global _token
    _token = token


def _extract(authorization: str | None, query_token: str | None) -> str | None:
    if query_token:
        return query_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:]
    return None


async def require_token(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> None:
    provided = _extract(authorization, token)
    if not _token or not provided or not secrets.compare_digest(provided, _token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing token")


async def require_token_ws(websocket: WebSocket, token: str | None) -> bool:
    """WebSockets can't set custom headers from the browser, so the token is
    always passed as a query param here instead of reusing require_token."""
    if not _token or not token or not secrets.compare_digest(token, _token):
        await websocket.close(code=4401)
        return False
    return True
