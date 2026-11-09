
from datetime import date
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

import schemas
from config import get_s3_storage_client, get_jwt_auth_manager
from database import (
    get_db,
    UserModel,
    UserGroupEnum,
    UserProfileModel,
)
from exceptions import (
    TokenExpiredError,
    InvalidTokenError,
    BaseS3Error,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=schemas.ProfileCreateResponseSchema,
    summary="Create a new user profile",
    description="Create a new user profile with avatar image",
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    s3_client: Annotated[
        S3StorageInterface,
        Depends(get_s3_storage_client),
    ],
    jwt_manager: Annotated[
        JWTAuthManagerInterface,
        Depends(get_jwt_auth_manager),
    ],
    first_name: str | None = Form(None),
    last_name: str | None = Form(None),
    gender: str | None = Form(None),
    date_of_birth: date | None = Form(None),
    info: str | None = Form(None),
    avatar: UploadFile | None = File(None),
):
    # 1. Extract and decode JWT token
    token = get_token(request=request)

    try:
        decoded_token = jwt_manager.decode_access_token(token=token)
        decoded_user_id = int(decoded_token["user_id"])
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )
    except (InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    # 2. Check permissions
    if decoded_user_id != user_id:
        current_user = await db.scalar(
            select(UserModel)
            .options(joinedload(UserModel.group))
            .where(UserModel.id == decoded_user_id)
        )

        if (
            current_user is None
            or not current_user.is_active
            or current_user.group is None
            or current_user.group.name != UserGroupEnum.ADMIN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )
    if any(
            value is None
            for value in (
                first_name,
                last_name,
                gender,
                date_of_birth,
                info,
                avatar,
            )
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="All profile fields are required.",
        )

    # 3. Check target user
    user = await db.scalar(
        select(UserModel).where(UserModel.id == user_id)
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    # 4. Check whether profile already exists
    existing_profile = await db.scalar(
        select(UserProfileModel).where(
            UserProfileModel.user_id == user_id
        )
    )

    if existing_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
        profile_data = schemas.ProfileCreateRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    file_data = await avatar.read()

    try:
        await s3_client.upload_file(
            file_name=avatar_key,
            file_data=file_data,
        )
    except BaseS3Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        ) from error

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        raise

    # 9. Generate avatar URL for response
    avatar_url = await s3_client.get_file_url(avatar_key)

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "gender": profile.gender,
        "date_of_birth": profile.date_of_birth,
        "info": profile.info,
        "avatar": avatar_url,
    }
