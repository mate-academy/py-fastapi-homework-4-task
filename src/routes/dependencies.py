from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, status, HTTPException
from typing import Annotated

from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager
from database import UserModel, get_db
from exceptions import TokenExpiredError, InvalidTokenError
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface


async def fetch_user_by_id(db: AsyncSession, user_id: int) -> UserModel:
    stmt = (
        select(UserModel)
        .where(UserModel.id == user_id)
        .options(selectinload(UserModel.group), selectinload(UserModel.profile))
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str, Depends(get_token)],
    jwt: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
) -> UserModel:
    """Get a user"""
    try:
        decoded_token = jwt.decode_access_token(access_token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )
    user_id = decoded_token.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )
    user = await fetch_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )
    return user
