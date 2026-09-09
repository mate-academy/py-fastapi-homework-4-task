from typing import Annotated

from config import get_s3_storage_client, get_jwt_auth_manager
from exceptions import BaseSecurityError, BaseS3Error
from fastapi import APIRouter, Depends, Form, HTTPException, status
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from storages import S3StorageInterface
from database import get_db, UserModel, UserGroupEnum, UserProfileModel

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201,
)
async def create_profile(
    user_id: int,
    profile_data: Annotated[ProfileRequestSchema, Form()],
    token: str = Depends(get_token),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):

    try:
        decoded_token = jwt_manager.decode_access_token(token)
        user_id_from_token = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    stmt = (
        select(UserModel).where(UserModel.id == user_id_from_token)
    ).options(joinedload(UserModel.group))

    db_user = await db.scalar(stmt)

    if (
        user_id_from_token != user_id
        and db_user.group.name == UserGroupEnum.USER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    existing_user = await db.scalar(
        select(UserModel).where(UserModel.id == user_id)
    )
    if not existing_user or not existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    existing_profile = await db.scalar(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    extension = profile_data.avatar.filename.split(".")[-1]
    file_name = f"avatars/{user_id}_avatar.{extension}"
    contents = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(file_name, contents)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    avatar_url = await s3_client.get_file_url(file_name)

    user_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=file_name,
    )

    db.add(user_profile)
    await db.commit()

    return ProfileResponseSchema(
        id=user_profile.id,
        user_id=user_profile.user_id,
        first_name=user_profile.first_name,
        last_name=user_profile.last_name,
        gender=user_profile.gender,
        date_of_birth=user_profile.date_of_birth,
        info=user_profile.info,
        avatar=avatar_url,
    )
