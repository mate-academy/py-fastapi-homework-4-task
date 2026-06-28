from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserGroupEnum, UserModel, UserProfileModel
from exceptions import BaseS3Error, BaseSecurityError, TokenExpiredError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    try:
        payload = jwt_manager.decode_access_token(parts[1])
    except TokenExpiredError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    current_user_id = payload.get("user_id")
    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )
    result = await db.execute(stmt)
    current_user = result.scalars().first()
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )
    return current_user


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    current_user: UserModel = Depends(get_current_user),
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    if current_user.id != user_id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_bytes = await profile_data.avatar.read()
    try:
        await s3_client.upload_file(avatar_key, avatar_bytes)
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
