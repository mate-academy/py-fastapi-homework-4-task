from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
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
from exceptions import BaseS3Error, InvalidTokenError, TokenExpiredError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()

def get_token(authorization: str | None = Header(default=None)) -> str:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )
    return token


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
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        ) from e

    token_user_id = payload.get("user_id")

    if token_user_id != user_id:
        result = await db.execute(
            select(UserModel)
            .options(joinedload(UserModel.group))
            .where(UserModel.id == token_user_id)
        )
        requester = result.scalar_one_or_none()
        if requester is None or requester.group.name != UserGroupEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    user = result.scalar_one_or_none()
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

    suffix = Path(profile_data.avatar.filename or "").suffix.lower() or ".jpg"
    avatar_key = f"avatars/{user_id}_avatar{suffix}"
    try:
        avatar_bytes = await profile_data.avatar.read()
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
    except BaseS3Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        ) from e

    try:
        profile = UserProfileModel(
            user_id=user_id,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            gender=GenderEnum(profile_data.gender),
            date_of_birth=profile_data.date_of_birth,
            info=profile_data.info,
            avatar=avatar_key,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation.",
        ) from e

    avatar_url = await s3_client.get_file_url(avatar_key)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender.value,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
