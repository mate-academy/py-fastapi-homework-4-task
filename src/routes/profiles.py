from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from pydantic import ValidationError

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_user_profile(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileResponseSchema:
    token = get_token(request)

    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error)
        ) from error

    current_user_stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == payload.get("user_id"))
    )
    current_user_result = await db.execute(current_user_stmt)
    current_user = current_user_result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if current_user.id != user_id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    target_user_stmt = (
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    target_user_result = await db.execute(target_user_stmt)
    target_user = target_user_result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if target_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    form_data = await request.form()
    try:
        profile_data = ProfileCreateSchema(
            first_name=form_data.get("first_name"),
            last_name=form_data.get("last_name"),
            gender=form_data.get("gender"),
            date_of_birth=form_data.get("date_of_birth"),
            info=form_data.get("info"),
            avatar=form_data.get("avatar")
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error

    avatar_bytes = await profile_data.avatar.read()
    avatar_suffix = Path(profile_data.avatar.filename or "avatar.jpg").suffix.lower() or ".jpg"
    avatar_key = f"avatars/{target_user.id}_avatar{avatar_suffix}"

    try:
        await s3_client.upload_file(avatar_key, avatar_bytes)
    except BaseS3Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        ) from error

    profile = UserProfileModel(
        user_id=target_user.id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key
    )

    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the profile."
        ) from error

    avatar_url = await s3_client.get_file_url(avatar_key)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )
