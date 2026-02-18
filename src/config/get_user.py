from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from database.models.accounts import UserModel
from config import get_jwt_auth_manager
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token


async def get_current_user(
    token: str = Depends(get_token),
    auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    try:
        payload = auth_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token validation failed")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    result = await db.execute(
        select(UserModel).where(UserModel.id == int(user_id)).options(selectinload(UserModel.group))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    return user
