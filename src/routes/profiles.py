from fastapi import APIRouter, Header, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from database import (
    get_db,
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    UserProfileModel,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    profile_data: ProfileCreateSchema = Depends(
        ProfileCreateSchema.from_request
    ),
) -> ProfileResponseSchema:
    """
    Create a new user profile.

    Args:
        user_id (int): The ID of the user to associate the profile with.
        token (str): Authorization bearer token.
        jwt_manager (JWTAuthManagerInterface): JWT manager for decoding the token.
        db (AsyncSession): Database session dependency.
        s3_client (S3StorageInterface): S3 client for avatar upload.
        profile_data (ProfileCreateSchema): Parsed and validated profile data.

    Returns:
        ProfileResponseSchema: The created profile with avatar URL.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )

    if current_user_id != user_id:
        group_stmt = (
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == current_user_id)
        )
        group_result = await db.execute(group_stmt)
        user_group = group_result.scalars().first()
        if not user_group or user_group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    existing_stmt = select(UserProfileModel).where(
        UserProfileModel.user_id == user_id
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_data = await profile_data.avatar.read()
    avatar_key = f"avatars/{user_id}_{profile_data.avatar.filename}"

    try:
        await s3_client.upload_file(
            file_name=avatar_key, file_data=avatar_data
        )
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3_client.get_file_url(avatar_key)

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
