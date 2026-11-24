from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import (
    get_db,
    UserModel,
    UserGroupEnum,
    UserProfileModel,
)
from database.models.accounts import GenderEnum
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import (
    ProfileCreateRequestSchema,
    ProfileResponseSchema,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()

AVATAR_EXTENSIONS = {"JPEG": "jpg", "JPG": "jpg", "PNG": "png"}


def get_avatar_extension(data: bytes) -> str:
    with Image.open(BytesIO(data)) as image:
        return AVATAR_EXTENSIONS[image.format]


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create user profile",
    description=(
        "Create a profile for a user. A user can create only their own "
        "profile, an admin can create a profile for any user."
    ),
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "User already has a profile."},
        401: {"description": "Invalid token or user is not active."},
        403: {"description": "No permission to edit this profile."},
        422: {"description": "Invalid profile data."},
        500: {"description": "Avatar upload failed."},
    },
)
async def create_profile(
        user_id: int,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        profile_data: ProfileCreateRequestSchema = Depends(
            ProfileCreateRequestSchema.as_form
        ),
) -> ProfileResponseSchema:
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )
    token_user_id = payload.get("user_id")

    if token_user_id != user_id:
        stmt = (
            select(UserModel)
            .options(joinedload(UserModel.group))
            .where(UserModel.id == token_user_id)
        )
        requester = (await db.execute(stmt)).scalars().first()
        if requester is None or not requester.has_group(UserGroupEnum.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    user = (await db.execute(stmt)).scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if user.profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_bytes = await profile_data.avatar.read()
    extension = get_avatar_extension(avatar_bytes)
    avatar_key = f"avatars/{user_id}_avatar.{extension}"
    try:
        await s3_client.upload_file(
            file_name=avatar_key, file_data=avatar_bytes
        )
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
        avatar=avatar_key,
    )
    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the profile.",
        )

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=await s3_client.get_file_url(avatar_key),
    )
