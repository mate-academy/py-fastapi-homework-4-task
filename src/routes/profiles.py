from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel
from database.models.accounts import GenderEnum
from exceptions import (
    BaseSecurityError,
    S3ConnectionError,
    S3FileUploadError,
)
from schemas.profiles import (
    UserProfileCreateSchema,
    UserProfileResponseSchema,
)
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter()


def get_token(
    authorization: str | None = Header(default=None),
) -> str:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Invalid Authorization header format. "
                "Expected 'Bearer <token>'"
            ),
        )

    return token


@router.post(
    "/users/{user_id}/profile/",
    response_model=UserProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    profile_data: UserProfileCreateSchema = Depends(
        UserProfileCreateSchema.as_form
    ),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    token_user_id = payload.get("user_id")

    if token_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    result = await db.execute(
        select(UserModel).where(UserModel.id == token_user_id)
    )
    authenticated_user = result.scalar_one_or_none()

    if authenticated_user is None or not authenticated_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    is_admin = authenticated_user.group_id == 3

    if token_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    result = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    target_user = result.scalar_one_or_none()

    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    result = await db.execute(
        select(UserProfileModel).where(
            UserProfileModel.user_id == user_id
        )
    )
    existing_profile = result.scalar_one_or_none()

    if existing_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    file_data = await profile_data.avatar.read()
    avatar_key = f"avatars/{user_id}_avatar.jpg"

    try:
        await s3_client.upload_file(
            file_name=avatar_key,
            file_data=file_data,
        )

        avatar_url = await s3_client.get_file_url(avatar_key)

    except (S3ConnectionError, S3FileUploadError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        ) from error

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=GenderEnum(profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    db.add(profile)

    try:
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        raise

    return UserProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender.value,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
