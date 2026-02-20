from fastapi import Depends, HTTPException, status
from fastapi.params import Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager
from database import get_db, UserModel
from exceptions import TokenExpiredError
from security.interfaces import JWTAuthManagerInterface

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def get_current_user(
    authorization: str | None = Header(None),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db)
):
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization.split(" ")[1]

    try:
        payload = jwt_manager.decode_access_token(token)

    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token."
        )

    user_id = payload.get("user_id")
    user = await db.scalar(
        select(UserModel)
        .options(
            joinedload(UserModel.group),
            joinedload(UserModel.profile),
        )
        .where(UserModel.id == user_id)
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    return user
