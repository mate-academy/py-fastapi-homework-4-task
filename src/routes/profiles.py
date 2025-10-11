import os
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
    File,
    UploadFile,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, UserGroupEnum, UserProfileModel, get_db
from exceptions import BaseSecurityError, BaseS3Error
from schemas import ProfileCreateRequestSchema, ProfileCreateResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileCreateResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileCreateResponseSchema:
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))

    current_user = await db.scalar(
        select(UserModel)
        .where(UserModel.id == payload.get("user_id"))
        .options(joinedload(UserModel.group))
    )
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    if not current_user.has_group(UserGroupEnum.ADMIN) and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to edit this profile.")

    existing_profile = await db.scalar(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if existing_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    validate_image(avatar)

    profile_data = ProfileCreateRequestSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date.fromisoformat(date_of_birth),
        info=info,
    )

    _, extension = os.path.splitext(avatar.filename)
    avatar_path = f"avatars/{user_id}_avatar{extension or '.jpg'}"

    try:
        await s3_client.upload_file(avatar_path, await avatar.read())
        avatar_url = await s3_client.get_file_url(avatar_path)
    except BaseS3Error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_path,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

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
