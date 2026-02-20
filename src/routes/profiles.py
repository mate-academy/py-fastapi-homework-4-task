from typing import cast
from fastapi import APIRouter, status, Depends, HTTPException
from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database.models.accounts import GenderEnum
from exceptions import S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from database import get_db, UserGroupModel, UserGroupEnum, UserModel, UserProfileModel
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def profile_create(
        user_id: int,
        data: ProfileRequestSchema = Depends(ProfileRequestSchema.from_form),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        token: str = Depends(get_token),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        db: AsyncSession = Depends(get_db),

):
    # Token Validation
    try:
        decode_token = jwt_manager.decode_access_token(token)
        token_user_id = decode_token.get("user_id")
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # Authorization Rules
    if user_id != token_user_id:
        request = await db.execute(
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == token_user_id)
        )
        user_group = request.scalar_one_or_none()
        if not user_group or user_group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    #  User Existence and Status
    request_user = await db.execute(
        select(UserModel)
        .where(UserModel.id == user_id)
    )
    user = request_user.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    # Check for Existing Profile
    user_profile = await db.execute(
        select(UserProfileModel)
        .where(UserProfileModel.user_id == user.id)
    )
    profile = user_profile.scalar_one_or_none()
    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # Avatar Upload to S3 Storage
    file_data = await data.avatar.read()
    file_name = f"avatars/{user_id}_{data.avatar.filename}"

    try:
        await s3_client.upload_file(file_name=file_name, file_data=file_data)
    except S3FileUploadError as e:
        print(f"Error message is {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Profile Creation and Storage
    profile_to_create = UserProfileModel(
        user_id=cast(int, user_id),
        first_name=data.first_name,
        last_name=data.last_name,
        gender=cast(GenderEnum, data.gender),
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=file_name
    )
    db.add(profile_to_create)
    await db.commit()
    await db.refresh(profile_to_create)

    avatar_url = await s3_client.get_file_url(profile_to_create.avatar)

    return ProfileResponseSchema(
        id=user_id,
        user_id=cast(int, user.id),
        first_name=profile_to_create.first_name,
        last_name=profile_to_create.last_name,
        gender=profile_to_create.gender,
        date_of_birth=profile_to_create.date_of_birth,
        info=profile_to_create.info,
        avatar=cast(HttpUrl, avatar_url)
    )
