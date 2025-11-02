from __future__ import annotations

import mimetypes
import os
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Request,
    Form,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ВІДНОСНІ імпорти (щоб PyCharm не підкреслював без PYTHONPATH)
from ..config.dependencies import (
    get_db,
    get_jwt_auth_manager,
    get_s3_storage_client,
)
from ..config.settings import BaseAppSettings, get_settings
from ..security.http import get_token
from ..security.interfaces import JWTAuthManagerInterface
from ..storages.interfaces import S3StorageInterface

from ..database.models.accounts import UserModel, UserProfileModel, GenderEnum

from ..schemas.profiles import (
    ProfileCreateSchema,
    ProfileResponseSchema,
    validate_avatar_bytes,
)

router = APIRouter(prefix="/users", tags=["profiles"])


@router.post(
    "/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    request: Request,  # важливо: до параметрів із дефолтами
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
    jwt_auth: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),

    # multipart/form-data
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str = Form(...),  # Pydantic перевірить формат/вік
    info: str = Form(...),
    avatar: UploadFile = File(...),
):
    """
    Вимоги з ТЗ:
    - 401: відсутній/неправильний/протермінований токен
    - 403: заборона створювати профіль іншому користувачу (крім підвищених ролей)
    - 401: користувач не існує або не активний
    - 400: профіль уже існує
    - 500: помилка завантаження аватара
    """

    # 1) Перевірка токена з Authorization
    token = get_token(request)
    try:
        payload = jwt_auth.decode_access_token(token)
    except Exception as e:
        # За вимогою — повертаємо саме цей detail
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        ) from e

    # Підтримуємо і "user_id", і "sub" як запасний варіант
    uid_claim = (payload or {}).get("user_id", (payload or {}).get("sub"))
    current_user_id = int(uid_claim) if isinstance(uid_claim, (int, str)) else None
    current_user_group = (payload or {}).get("group")

    if current_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )

    # 2) Авторизація: або сам собі, або підвищена роль
    is_self = (current_user_id == user_id)
    is_privileged = str(current_user_group or "").upper() in {"ADMIN", "MODERATOR"}
    if not (is_self or is_privileged):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # 3) Перевіряємо користувача і активність
    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user_res = await db.execute(user_stmt)
    user: UserModel | None = user_res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    # 4) Чи немає вже профілю
    profile_stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    profile_res = await db.execute(profile_stmt)
    if profile_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    # 5) Валідація бізнес-даних (без файлу)
    create_schema = ProfileCreateSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
    )

    # 6) Валідація файлу
    file_bytes = await avatar.read()
    try:
        validate_avatar_bytes(avatar.filename or "", avatar.content_type, file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # 7) Завантаження в S3/MinIO
    guessed_ext = None
    if avatar.content_type:
        guessed_ext = mimetypes.guess_extension(avatar.content_type)
    if not guessed_ext:
        _, ext = os.path.splitext(avatar.filename or "")
        guessed_ext = ext or ".jpg"

    object_name = f"avatars/{user_id}_{uuid4().hex}{guessed_ext}"

    try:
        # upload (спершу очікуваний фейком інтерфейс)
        if hasattr(s3_client, "upload_bytes"):
            await s3_client.upload_bytes(file_bytes, object_name, avatar.content_type)
        else:
            # fallback
            await s3_client.put_object(file_bytes, object_name, avatar.content_type)  # type: ignore[attr-defined]

        # url (спершу очікуваний фейком інтерфейс)
        if hasattr(s3_client, "get_object_url"):
            avatar_url = s3_client.get_object_url(object_name)
        else:
            # fallback
            avatar_url = s3_client.url_for(object_name)  # type: ignore[attr-defined]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    # 8) Зберігаємо профіль (gender → Enum, timezone-aware)
    now_utc = datetime.now(timezone.utc)
    profile = UserProfileModel(
        first_name=create_schema.first_name,
        last_name=create_schema.last_name,
        gender=GenderEnum(create_schema.gender),
        date_of_birth=create_schema.date_of_birth,
        info=create_schema.info,
        avatar=object_name,  # у БД — ключ; у відповіді — повний URL
        user_id=user.id,
        **({"created_at": now_utc} if hasattr(UserProfileModel, "created_at") else {}),
        **({"updated_at": now_utc} if hasattr(UserProfileModel, "updated_at") else {}),
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # 9) Відповідь
    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender.value if hasattr(profile.gender, "value") else profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
