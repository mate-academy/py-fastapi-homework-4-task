import mimetypes
import os
from datetime import date
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    status,
    HTTPException,
    Request,
    Form,
    File,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from database.models.accounts import GenderEnum
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileCreateResponseSchema
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


async def verify_token_and_get_user_id(
    request: Request,
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> int:
    """
    Helper function to verify token and get user ID.
    Returns exact error message for expired tokens.
    """
    token = get_token(request)

    try:
        decoded = jwt_manager.decode_access_token(token)
        current_user_id = decoded.get("user_id")
    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )

    return current_user_id


def validated_name(v: str) -> str:
    try:
        validate_name(v)
        return v.lower()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def validated_gender(v: str) -> str:
    try:
        validate_gender(v)
        return v
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def validated_birth_date(v: date) -> date:
    try:
        validate_birth_date(v)
        return v
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def validated_info(v: str) -> str:
    try:
        validate_info(v)
        return v
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def validated_avatar(v: UploadFile) -> UploadFile:
    try:
        validate_image(v)
        return v
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    gender: Annotated[str, Form()],
    date_of_birth: Annotated[date, Form()],
    info: Annotated[str, Form()],
    avatar: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(get_token)],
    jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
    s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
) -> ProfileCreateResponseSchema:
    first_name = validated_name(first_name)
    last_name = validated_name(last_name)
    gender = validated_gender(gender)
    date_of_birth = validated_birth_date(date_of_birth)
    info = validated_info(info)
    avatar = validated_avatar(avatar)

    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )

    current_user = await db.scalar(
        select(UserModel)
        .where(UserModel.id == decoded_token.get("user_id"))
        .options(joinedload(UserModel.group))
    )

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if not current_user.has_group(UserGroupEnum.ADMIN) and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    user_for_profile = await db.scalar(
        select(UserModel)
        .where(UserModel.id == user_id)
        .options(joinedload(UserModel.profile))
    )

    if not user_for_profile or not user_for_profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if user_for_profile.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    _, extension = os.path.splitext(avatar.filename or "")
    if not extension:
        extension = ".jpg"

    avatar_path = f"avatars/{user_id}_avatar{extension}"

    avatar.file.seek(0)
    file_content = avatar.file.read()

    content_type = mimetypes.guess_type(avatar.filename or "")[0]
    if not content_type:
        content_type = "application/octet-stream"

    try:
        await s3_client.upload_file(
            avatar_path, file_content, content_type=content_type
        )
        avatar_url = await s3_client.get_file_url(avatar_path)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        first_name=first_name,
        last_name=last_name,
        gender=GenderEnum(gender),
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar_path,
        user=user_for_profile,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileCreateResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender.value,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
