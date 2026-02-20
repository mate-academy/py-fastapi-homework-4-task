import secrets
from fastapi import Header, Depends, HTTPException, status

from config import get_jwt_auth_manager
from security.interfaces import JWTAuthManagerInterface
from exceptions import TokenExpiredError


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a secure random token.

    Returns:
        str: Securely generated token.
    """
    return secrets.token_urlsafe(length)


async def require_authorization(
    authorization: str | None = Header(None),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> int:
    """
    Dependency that ensures Authorization header is valid and returns the token's user_id.
    This runs before body parsing because it only depends on headers and other non-body deps.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header is missing")

    auth_header_list = authorization.split()
    if len(auth_header_list) != 2 or auth_header_list[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = auth_header_list[1]
    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    return payload["user_id"]
