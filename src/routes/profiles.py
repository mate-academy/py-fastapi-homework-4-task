from __future__ import annotations

import mimetypes
import os
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.dependencies import (
    get_db,
    get_settings,
    get_jwt_auth_manager,
    get_s3_storage_client,
)
from config.settings import BaseAppSettings
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface

from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema, validate_avatar_bytes
from schemas.accounts import TokenPayloadSchema  # якщо є окрема схема для payload; інакше не використовуй
from security.http import get_token  # твій геттер токена з заголовка
from database.models.accounts import UserModel, UserGroupEnum
from database.models.movies import  # не потрібно
from database.models import accounts as acc_models
from database.models import base as base_models
from database.models.accounts import UserProfileModel

router = APIRouter(prefix="/users", tags=["profiles"])



# src/routes/profiles.py
@router.post("/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
    user_id: int,
    # профільні поля приходять як form-data разом з файлом (типова поведінка e2e тестів)
    first_name: str = Depends(),
    last_name: str = Depends(),
    gender: str = Depends(),
    date_of_birth: str = Depends(),  # парсимо далі пидантиком
    info: str = Depends(),
    avatar: UploadFile = File(...),

    request: Request = None,
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
    jwt_auth: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    """
    Правила з умови:
    - 401: відсутній/некоректний/протермінований токен
    - 403: користувач без прав на створення чужого профілю
    - 401: user не існує або не активний
    - 400: профіль уже існує
    - 500: помилка завантаження аватару
    """
    # 1) Перевірка токена
    token = get_token(request)  # може кинути 401 з відповідним detail
    try:
        payload = jwt_auth.decode_access_token(token)  # має кинути на прострочений/невалідний
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")  # за умовою

    current_user_id = int(payload.get("sub")) if isinstance(payload.get("sub"), (str, int)) else None
    current_user_group = payload.get("group")  # очікуємо щось як "ADMIN"/"USER"/...

    if current_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    # 2) Авторизація: або сам собі, або адмін/модератор
    is_self = current_user_id == user_id
    is_privileged = str(current_user_group or "").upper() in {"ADMIN", "MODERATOR"}
    if not (is_self or is_privileged):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to edit this profile.")

    # 3) Перевірка користувача і активності
    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user_res = await db.execute(user_stmt)
    user: UserModel | None = user_res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    # 4) Перевірка на існуючий профіль
    profile_stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    profile_res = await db.execute(profile_stmt)
    existing = profile_res.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    # 5) Валідація бізнес-даних через Pydantic (без файлу)
    try:
        create_schema = ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
        )
    except Exception as e:
        # FastAPI сам перетворить на 422, але за потреби можна явно
        raise

    # 6) Зчитуємо файл та валідуємо зображення
    file_bytes = await avatar.read()
    try:
        validate_avatar_bytes(avatar.filename or "", avatar.content_type, file_bytes)
    except Exception:
        # валідація файлу = 422 або 400; у вимогах конкретного мапінгу немає, залишимо 422 дефолтно
        raise

    # 7) Завантаження у S3
    # Визначимо розширення
    guessed_ext = None
    if avatar.content_type:
        guessed_ext = mimetypes.guess_extension(avatar.content_type)
    if not guessed_ext:
        # fallback за іменем
        _, ext = os.path.splitext(avatar.filename or "")
        guessed_ext = ext or ".jpg"

    object_name = f"avatars/{user_id}_{uuid4().hex}{guessed_ext}"

    try:
        # очікувана інтерфейсна сигнатура:
        # upload_bytes(data: bytes, object_name: str, content_type: str | None) -> None
        await s3_client.upload_bytes(file_bytes, object_name, avatar.content_type)
        avatar_url = s3_client.get_object_url(object_name)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    # 8) Зберігаємо профіль
    profile = UserProfileModel(
        first_name=create_schema.first_name.lower(),
        last_name=create_schema.last_name.lower(),
        gender=create_schema.gender,
        date_of_birth=create_schema.date_of_birth,
        info=create_schema.info,
        avatar=object_name,  # у моделі можна тримати ключ; у відповіді — повний URL
        user_id=user.id,
        created_at=datetime.utcnow() if hasattr(UserProfileModel, "created_at") else None,
        updated_at=datetime.utcnow() if hasattr(UserProfileModel, "updated_at") else None,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # 9) Формуємо відповідь (avatar — як повний URL)
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

ть