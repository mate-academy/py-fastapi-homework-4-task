from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import (
    get_s3_storage_client,
    get_jwt_auth_manager,
    get_settings,
    BaseAppSettings,
)
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from database.models.accounts import GenderEnum
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    description="Create a profile for a user.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "User already has a profile."},
        401: {"description": "User not found or not active / Token has expired."},
        403: {"description": "You don't have permission to edit this profile."},
        404: {"description": "User not found."},
        500: {"description": "Failed to upload avatar. Please try again later."},
    },
)
async def create_user_profile(
    user_id: int,
    profile_data: Annotated[ProfileCreateSchema, Depends(ProfileCreateSchema.as_form)],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
    token: Annotated[str, Depends(get_token)],
    jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
    settings: Annotated[BaseAppSettings, Depends(get_settings)],
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    token_user_id = payload.get("user_id")

    token_user_result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == token_user_id)
    )
    token_user = token_user_result.scalars().first()

    if not token_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    target_user = await db.get(UserModel, user_id)
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if token_user_id != user_id and token_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    existing_profile_result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if existing_profile_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_file = profile_data.avatar
    avatar_path = f"avatars/{user_id}_{avatar_file.filename}"
    file_contents = await avatar_file.read()

    try:
        await s3_client.upload_file(file_name=avatar_path, file_data=file_contents)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=GenderEnum(profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_path,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = (
        f"{settings.S3_STORAGE_ENDPOINT}/{settings.S3_BUCKET_NAME}/{avatar_path}"
    )

    response_data = profile.__dict__
    response_data["avatar"] = avatar_url

    return ProfileResponseSchema.model_validate(response_data)
