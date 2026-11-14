import logging
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserGroupEnum, UserModel, UserProfileModel
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema, profile_from_form
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def get_profile_requester(
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    try:
        token_data = jwt_manager.decode_access_token(token)
        requester_id = token_data.get("user_id")
        if isinstance(requester_id, bool) or not isinstance(requester_id, int) or requester_id < 1:
            raise ValueError("Invalid token.")
    except (BaseSecurityError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    result = await db.execute(
        select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == requester_id)
    )
    requester = result.scalar_one_or_none()
    if not requester or not requester.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")
    return requester


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
        user_id: int,
        requester: UserModel = Depends(get_profile_requester),
        profile_data: ProfileCreateSchema = Depends(profile_from_form),
        db: AsyncSession = Depends(get_db),
        storage: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:

    if requester.id != user_id and (not requester.group or requester.group.name != UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    target = await db.get(UserModel, user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    existing = await db.execute(select(UserProfileModel.id).where(UserProfileModel.user_id == user_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    avatar_bytes = await profile_data.avatar.read()
    with Image.open(BytesIO(avatar_bytes)) as image:
        extension = "png" if image.format == "PNG" else "jpg"
    avatar_key = f"avatars/{user_id}_avatar.{extension}"

    profile = UserProfileModel(user_id=user_id, avatar=avatar_key, **profile_data.model_dump(exclude={"avatar"}))
    db.add(profile)
    try:
        await db.flush()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create profile."
        ) from error

    try:
        await storage.upload_file(avatar_key, avatar_bytes)
        avatar_url = await storage.get_file_url(avatar_key)
        await db.commit()
    except (BaseS3Error, SQLAlchemyError) as error:
        try:
            await storage.delete_file(avatar_key)
        except BaseS3Error:
            logging.exception("Failed to remove avatar after profile creation failed.")
        await db.rollback()
        detail = "Failed to upload avatar. Please try again later."
        if isinstance(error, SQLAlchemyError):
            detail = "Failed to create profile."
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail) from error

    return ProfileResponseSchema(
        id=profile.id,
        user_id=user_id,
        avatar=avatar_url,
        **profile_data.model_dump(exclude={"avatar"}),
    )
