from typing import Annotated, cast

from fastapi import APIRouter, status, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_s3_storage_client
from database import UserModel, get_db, UserGroupEnum, UserProfileModel
from exceptions import BaseS3Error
from routes.dependencies import get_user, fetch_user_by_id
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    user: Annotated[UserModel, Depends(get_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
    profile_data: Annotated[ProfileCreateSchema, Form()],
) -> ProfileResponseSchema:
    target_user_id = user_id
    if target_user_id != user.id and not user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )
    target_user = await fetch_user_by_id(db, user_id=target_user_id)
    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if target_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    contents = await profile_data.avatar.read()
    filename = f"avatars/{target_user_id}_{profile_data.avatar.filename}"
    try:
        await s3_client.upload_file(filename, contents)
        s3_url = await s3_client.get_file_url(filename)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        **profile_data.model_dump(exclude={"avatar"}),
        avatar=filename,
        user_id=user_id,
    )
    new_profile.user_id = target_user_id
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=s3_url,
    )
