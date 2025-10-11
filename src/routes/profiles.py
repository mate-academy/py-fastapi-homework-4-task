import os
from datetime import datetime, date

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
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info,
)

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
        raise HTTPException(status_code=401, detail="User not found or not active.")
    if not current_user.has_group(UserGroupEnum.ADMIN) and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    existing_profile = await db.scalar(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if existing_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    validate_name(first_name)
    validate_name(last_name)
    validate_gender(gender)
    validate_info(info)

    try:
        parsed_date = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        validate_birth_date(parsed_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    validate_image(avatar)

    await avatar.seek(0)

    _, extension = os.path.splitext(avatar.filename)
    avatar_path = f"avatars/{user_id}_avatar{extension or '.jpg'}"

    try:
        await s3_client.upload_file(avatar_path, await avatar.read())
        avatar_url = await s3_client.get_file_url(avatar_path)
    except BaseS3Error:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower(),
        last_name=last_name.lower(),
        gender=gender,
        date_of_birth=parsed_date,
        info=info,
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
