import os
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileCreateRequestSchema, ProfileCreateResponseSchema
from security.http import get_token
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(get_token)],
    jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
    s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str | None = Form(None),
    avatar: UploadFile = File(...),
) -> ProfileCreateResponseSchema:
    try:
        token = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))
    current_user = await db.scalar(
        select(UserModel)
        .where(UserModel.id == token.get("user_id"))
        .options(joinedload(UserModel.group))
    )
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")
    if not current_user.has_group(UserGroupEnum.ADMIN) and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")
    user_for_profile = await db.scalar(
        select(UserModel).where(UserModel.id == user_id).options(joinedload(UserModel.profile))
    )
    if user_for_profile.profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    # --- Робота з аватаром ---
    _, extension = os.path.splitext(avatar.filename)
    avatar_path = f"avatars/{user_id}_avatar{extension}"
    file_bytes = await avatar.read()
    try:
        await s3_client.upload_file(avatar_path, file_bytes)
        avatar_url = await s3_client.get_file_url(avatar_path)
    except BaseS3Error:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    # --- Валідація текстових полів через Pydantic ---
    profile_data = ProfileCreateRequestSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
    )

    # --- Створення профілю ---
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