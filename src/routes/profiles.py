from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import HttpUrl

from database import get_db
from database.models.accounts import UserModel, UserProfileModel, GenderEnum, UserGroupModel, UserGroupEnum
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from config.get_user import get_current_user
from config import get_s3_storage_client
from storages import S3StorageInterface
from exceptions import S3FileUploadError

router = APIRouter(tags=["profiles"])


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    user_id: int,
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    # Перевірка доступу
    is_admin = getattr(current_user, "group_id", None) == 3
    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    # Перевірка на існуючий профіль
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    # Завантаження аватара
    avatar_bytes = await profile_data.avatar.read()
    avatar_key = f"avatars/{user_id}_{profile_data.avatar.filename}"
    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Створення профілю
    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=cast(GenderEnum, profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    avatar_url = await s3_client.get_file_url(new_profile.avatar)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=cast(HttpUrl, avatar_url)
    )
