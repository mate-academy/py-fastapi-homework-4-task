from datetime import date
from typing import Optional

from fastapi import APIRouter, Form, UploadFile, File, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import get_s3_storage_client
from config.dependencies import get_current_user_id
from database import get_db, UserModel, UserProfileModel

from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from storages import S3StorageInterface
from validation import validate_image

router = APIRouter()


@router.post("/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    user_id: int,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    date_of_birth: Optional[date] = Form(None),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    current_user_id: int = Depends(get_current_user_id)
):
    try:
        ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info
        )
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )
    current_user = result.scalars().first()
    if not current_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user_id != user_id and not current_user.group.name == "admin":
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    user = await db.get(UserModel, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    existing_profile = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if existing_profile.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already has a profile.")

    avatar_bytes = await avatar.read()

    filename = f"avatars/{user_id}_avatar.jpg"
    try:
        await s3_client.upload_file(file_data=avatar_bytes, file_name=filename)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower() if first_name else None,
        last_name=last_name.lower() if last_name else None,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=filename,
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
        avatar=await s3_client.get_file_url(profile.avatar),
    )
