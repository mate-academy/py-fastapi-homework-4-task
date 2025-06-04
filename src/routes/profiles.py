from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    status,
    File,
    UploadFile,
    Path,
    Form,
    HTTPException,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql.expression import select

from config import get_jwt_auth_manager, get_s3_storage_client
from database.models.accounts import GenderEnum
from exceptions import TokenExpiredError, InvalidTokenError, S3FileUploadError
from schemas.profiles import (
    UserProfileBase,
    CreateUserProfileRequest,
    CreateUserProfileResponse,
)
from security.http import get_token
from security.token_manager import JWTAuthManager

from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from storages import S3StorageInterface

router = APIRouter()

# Write your code here


@router.post(
    "/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    profile_data: Annotated[CreateUserProfileRequest, Form()],
    user_id: int = Path(),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> CreateUserProfileResponse:
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token has expired.",
        )
    except InvalidTokenError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    try:
        request_user = await db.scalar(
            select(UserModel)
            .where(UserModel.id == decoded_token["user_id"])
            .options(
                joinedload(UserModel.group),
                joinedload(UserModel.profile),
            )
        )

        user: UserModel = await db.scalar(
            select(UserModel)
            .where(UserModel.id == user_id)
            .options(
                joinedload(UserModel.profile),
            )
        )

        if not user or not user.is_active:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "User not found or not active.",
            )

        if (
            not request_user.has_group(UserGroupEnum.ADMIN)
            and request_user.id != user_id
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You don't have permission to edit this profile.",
            )

        if user.profile:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "User already has a profile.",
            )
    except SQLAlchemyError:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            (
                "Failed to create new profile in database. "
                "Please try again later."
            ),
        )

    try:
        avatar_key = f"avatars/{user_id}_avatar.jpg"
        await s3_client.upload_file(
            avatar_key, await profile_data.avatar.read()
        )
    except S3FileUploadError:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user=user,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        date_of_birth=profile_data.date_of_birth,
        gender=profile_data.gender,
        info=profile_data.info,
        avatar=avatar_key,
    )

    db.add(profile)

    await db.commit()

    profile.avatar = await s3_client.get_file_url(avatar_key)

    return profile
