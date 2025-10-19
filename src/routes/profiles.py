import os
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, Form
from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_s3_storage_client, get_jwt_auth_manager
from database import UserModel, UserGroupEnum, UserProfileModel
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileCreateResponseSchema, ProfileCreateRequestSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from database import get_db
from security.http import get_token

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    profile_data: Annotated[ProfileCreateRequestSchema, Form()],
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(get_token)],
    jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
    s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
) -> ProfileCreateResponseSchema:
    try:
        try:
            token = jwt_manager.decode_access_token(token)
        except BaseSecurityError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error)
            )
        current_user = await db.scalar(
            select(
                UserModel
            ).where(
                UserModel.id == token.get("user_id")
            ).options(
                joinedload(UserModel.group),
            )
        )
        if not current_user or not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )
        if not current_user.has_group(UserGroupEnum.ADMIN) and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )
        user_for_profile = await db.scalar(
            select(
                UserModel
            ).where(
                UserModel.id == user_id
            ).options(
                joinedload(UserModel.profile),
            )
        )
        if user_for_profile.profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a profile."
            )
        _, extension = os.path.splitext(profile_data.avatar.filename)
        avatar_path = f"avatars/{user_id}_avatar{extension}"
        file = await profile_data.avatar.read()
        try:
            await s3_client.upload_file(avatar_path, file)
            avatar_url = await s3_client.get_file_url(avatar_path)
        except BaseS3Error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later."
            )
        profile = UserProfileModel(
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            gender=profile_data.gender,
            date_of_birth=profile_data.date_of_birth,
            info=profile_data.info,
            avatar=avatar_path,
            user=user_for_profile,
        )
        db.add(profile)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating profile."
        )

    return ProfileCreateResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
