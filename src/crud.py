from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db

from src.database import UserModel


async def get_user_by_id(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.execute(UserModel).filter(UserModel.id == user_id).first()

    return user
