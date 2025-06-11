from typing import Annotated
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from database.session_postgresql import get_postgresql_db  # ✅ Исправленный импорт
from config.dependencies import (
    get_s3_storage_client,
    get_token,
    get_jwt_auth_manager,
)
from database.models.accounts import UserModel, UserProfileModel, GenderEnum
from schemas.profiles import UserProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image, validate_birth_date

router = APIRouter(prefix="/users", tags=["Profiles"])


@router.post("/{user_id}/profile/", response_model=UserProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
    user_id: int,
    first_name: Annotated[str, Form(...)],
    last_name: Annotated[str, Form(...)],
    gender: Annotated[str, Form(...)],
    date_of_birth: Annotated[str, Form(...)],
    info: Annotated[str, Form(...)],
    avatar: Annotated[UploadFile, File(...)],
    token: Annotated[str, Depends(get_token)],
    db: Annotated[AsyncSession, Depends(get_postgresql_db)],
    jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
    s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
):
    # 🔐 Проверка и декодирование токена
    try:
        payload = jwt_manager.decode_access_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token is invalid or expired.")

    token_user_id = int(payload.get("sub") or 0)
    if not token_user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    # 🔎 Получение пользователя
    user: UserModel | None = await db.get(UserModel, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    # 🔒 Авторизация
    if user_id != token_user_id and not user.has_group(GenderEnum.ADMIN):  # ❗Исправь GenderEnum на UserGroupEnum, если нужно
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    # 🔄 Проверка: профиль уже существует
    if user.profile is not None:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    # 📸 Валидация изображения
    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 📅 Проверка даты рождения
    try:
        parsed_birth_date = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        validate_birth_date(parsed_birth_date)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ☁️ Загрузка аватара
    avatar_content = await avatar.read()
    avatar_filename = f"avatars/{user_id}_{avatar.filename}"
    try:
        await s3_client.upload_file(avatar_filename, avatar_content)
        avatar_url = await s3_client.get_file_url(avatar_filename)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    # 📝 Создание профиля
    profile = UserProfileModel(
        first_name=first_name,
        last_name=last_name,
        gender=GenderEnum(gender),
        date_of_birth=parsed_birth_date,
        info=info,
        avatar=avatar_url,
        user_id=user_id,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return profile
