from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.database.models.profiles import UserProfileModel
from src.schemas.profiles import UserProfileCreate, UserProfileUpdate


async def get_profile_by_user_id(db: AsyncSession, user_id: int) -> UserProfileModel | None:
    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    return result.scalars().first()


async def create_profile(db: AsyncSession, user_id: int, profile_data: UserProfileCreate) -> UserProfileModel:
    new_profile = UserProfileModel(user_id=user_id, **profile_data.dict())
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return new_profile


async def update_profile(db: AsyncSession, profile: UserProfileModel, update_data: UserProfileUpdate) -> UserProfileModel:
    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(profile, key, value)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile