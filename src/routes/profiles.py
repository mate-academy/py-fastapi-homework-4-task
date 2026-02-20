from typing import Annotated

from fastapi import APIRouter, status, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserGroupEnum, UserModel, UserProfileModel
from exceptions import InvalidTokenError, TokenExpiredError, S3ConnectionError, S3FileUploadError
from schemas import ProfileResponseSchema, ProfileFormData
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    status_code=status.HTTP_201_CREATED,
)
async def profile_user(
    user_id: int,
    form: Annotated[ProfileFormData, Form()],
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileResponseSchema:
    try:
        payload = jwt_manager.decode_access_token(token)
    except (InvalidTokenError, TokenExpiredError) as e:
        raise HTTPException(status_code=401, detail=str(e))

    request_user_id = payload["user_id"]

    user = await db.scalar(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == request_user_id)
    )

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if user_id != user.id and user.group.name != UserGroupEnum.ADMIN.value:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    exist_profile = await db.scalar(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if exist_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    avatar_bytes = await form.avatar.read()
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_url = ""
    try:
        await s3_client.upload_file(avatar_key, avatar_bytes)
        avatar_url = await s3_client.get_file_url(avatar_key)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        user_id=user_id,
        first_name=form.first_name,
        last_name=form.last_name,
        gender=form.gender,
        date_of_birth=form.date_of_birth,
        info=form.info,
        avatar=avatar_key
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

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
