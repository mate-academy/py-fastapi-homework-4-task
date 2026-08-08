from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import (
    get_jwt_auth_manager,
    get_s3_storage_client,
)
from database import (
    UserGroupEnum,
    UserModel,
    UserProfileModel,
    get_db,
)
from database.models.accounts import GenderEnum
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import (
    ProfileCreateSchema,
    ProfileResponseSchema,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    token: str = Depends(get_token),
    profile_data: ProfileCreateSchema = Depends(
        ProfileCreateSchema.as_form
    ),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(
        get_jwt_auth_manager
    ),
    s3_client: S3StorageInterface = Depends(
        get_s3_storage_client
    ),
) -> ProfileResponseSchema:

    # Проверяем JWT.
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    current_user_id = payload.get("user_id")

    if current_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    # Находим пользователя, который делает запрос.
    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )

    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    # Обычный пользователь может создать профиль только себе.
    # Admin может создать профиль другому пользователю.
    if (
        current_user.id != user_id
        and not current_user.has_group(UserGroupEnum.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # Проверяем пользователя, которому создаём профиль.
    stmt = select(UserModel).where(
        UserModel.id == user_id,
        UserModel.is_active.is_(True),
    )

    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    # Проверяем, нет ли уже профиля.
    stmt = select(UserProfileModel).where(
        UserProfileModel.user_id == user_id
    )

    result = await db.execute(stmt)
    existing_profile = result.scalars().first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    # Читаем avatar.
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_data = await profile_data.avatar.read()

    # Загружаем avatar в MinIO/S3.
    try:
        await s3_client.upload_file(
            avatar_key,
            avatar_data,
        )
    except BaseS3Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to upload avatar. "
                "Please try again later."
            ),
        ) from error

    # Создаём профиль.
    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=GenderEnum(profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    db.add(profile)

    await db.commit()
    await db.refresh(profile)

    # Получаем полный URL картинки.
    avatar_url = await s3_client.get_file_url(
        avatar_key
    )

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
