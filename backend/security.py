import hmac

from fastapi import Header, HTTPException, status

from backend.config import settings


async def require_backend_token(x_backend_token: str = Header(default="")) -> None:
    expected = settings.backend_access_token
    if not expected:
        return

    if not x_backend_token or not hmac.compare_digest(x_backend_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid backend access token.",
        )
