from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_s3_storage_client
from database import get_db, UserModel
from database.models.accounts import UserProfileModel
from exceptions.storage import S3FileUploadError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.auth import get_current_user
from storages.interfaces import S3StorageInterface

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


def _is_admin(user: UserModel) -> bool:
    # чтобы не триггерить lazy-load group relationship
    return getattr(user, "group_id", None) == 3


@router.post(
    "/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProfileResponseSchema,
)
async def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    storage: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    # 1) user_id должен существовать и быть active
    stmt_user = select(UserModel).where(UserModel.id == user_id)
    user_obj = (await db.execute(stmt_user)).scalars().first()
    if not user_obj or not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    # 2) права
    if current_user.id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # 3) нельзя создать второй раз
    stmt_existing = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    existing = (await db.execute(stmt_existing)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    # 4) читаем файл (bytes)
    avatar_bytes = await avatar.read()

    # 5) валидация через ProfileCreateSchema (как требуют тесты/ревью)
    try:
        payload = ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar_bytes,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"

    try:
        await storage.upload_file(file_name=avatar_key, file_data=avatar_bytes)
        avatar_url = await storage.get_file_url(avatar_key)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        info=payload.info,
        avatar=avatar_key,  # в БД ключ
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # в ответе отдаём url
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
