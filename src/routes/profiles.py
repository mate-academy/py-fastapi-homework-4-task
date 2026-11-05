from fastapi import (
    APIRouter,
    Depends,
    status,
    HTTPException
)
from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from exceptions import BaseSecurityError, BaseS3Error

from config import get_jwt_auth_manager, get_s3_storage_client
from security.http import get_token
from schemas.profiles import (
    ProfileResponseSchema,
    ProfileCreateSchema
)
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
        user_id: int,
        token: str = Depends(get_token),
        profile_data: ProfileCreateSchema = Depends(
            ProfileCreateSchema.as_form
        ),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    target_user_id = user_id
    authenticated_user_id = decoded_token.get("user_id")

    if authenticated_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    statement = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == authenticated_user_id)
    )
    result = await db.execute(statement)
    authenticated_user = result.scalars().first()

    if not authenticated_user or not authenticated_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    is_admin = authenticated_user.has_group(
        UserGroupEnum.ADMIN
    )

    if authenticated_user_id != target_user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    target_statement = (
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == target_user_id)
    )
    target_result = await db.execute(target_statement)
    target_user = target_result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if target_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_data = await profile_data.avatar.read()
    avatar_key = f"avatars/{target_user_id}_avatar.jpg"

    try:
        await s3_client.upload_file(
            file_name=avatar_key,
            file_data=avatar_data,
        )
        avatar_url = await s3_client.get_file_url(avatar_key)
    except BaseS3Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        ) from error

    profile = UserProfileModel(
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
        user_id=target_user_id,
    )

    db.add(profile)
    try:
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation."
        ) from e

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=HttpUrl(avatar_url),
    )
