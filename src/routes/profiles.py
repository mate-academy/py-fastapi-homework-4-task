from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserGroupEnum, UserModel, UserProfileModel, get_db
from exceptions import BaseS3Error, BaseSecurityError
from schemas import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user profile",
)
async def create_user_profile(
    user_id: int,
    token: str = Depends(get_token),
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    try:
        token_data = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    authenticated_user_id = token_data.get("user_id")
    authenticated_user_result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == authenticated_user_id)
    )
    authenticated_user = authenticated_user_result.scalars().first()

    if not authenticated_user or not authenticated_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if (
        authenticated_user.id != user_id
        and not authenticated_user.has_group(UserGroupEnum.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    target_user_result = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    target_user = target_user_result.scalars().first()
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    existing_profile_result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if existing_profile_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    suffix = Path(profile_data.avatar.filename or "avatar.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        suffix = ".jpg"
    avatar_key = f"avatars/{user_id}_avatar{suffix}"
    avatar_data = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(avatar_key, avatar_data)
        avatar_url = await s3_client.get_file_url(avatar_key)
    except BaseS3Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        ) from error

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )
    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation.",
        ) from error

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
