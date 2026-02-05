from datetime import date
from typing import cast

from fastapi import Form, UploadFile, File
from pydantic import ValidationError
from sqlalchemy import select

from src.database.models.accounts import GenderEnum
from src.exceptions import TokenExpiredError, InvalidTokenError
from src.security.interfaces import JWTAuthManagerInterface
from src.schemas.profiles import ProfileRequestSchema, ProfileResponseSchema, TokenData
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import get_s3_storage_client
from src.storages import S3StorageInterface
from src.config import get_jwt_auth_manager
from src.database import (
    get_db,
    UserModel,
    UserProfileModel,
)
from src.security.http import get_token

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
        user_id: int,

        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),

        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        profile = ProfileRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )
    except (ValidationError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid."
        )

    token_user_id = payload.get("user_id")

    if token_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid."
        )

    if int(token_user_id) != user_id:
        request = await db.execute(
            select(UserModel).where(UserModel.id == int(token_user_id)),
        )
        request_user = request.scalar_one_or_none()
        is_admin_db = request_user and request_user.group_id == 3
        is_admin_token = payload.get("is_admin", False)
        if not (is_admin_db or is_admin_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    user_query = await db.execute(
        select(UserModel)
        .where(
            UserModel.id == user_id,
            UserModel.is_active == True  # noqa
        )
    )
    user = user_query.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    profile_query = await db.execute(
        select(UserProfileModel)
        .where(UserProfileModel.user_id == user_id)
    )
    existing_profile = profile_query.scalar_one_or_none()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    await avatar.seek(0)
    file_ext = avatar.filename.split(".")[-1].lower()
    file_name = f"avatars/{user_id}_avatar.{file_ext}"
    file_data = await avatar.read()

    try:
        await s3_client.upload_file(file_name=file_name, file_data=file_data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=cast(GenderEnum, profile.gender),
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=file_name,
    )

    db.add(new_profile)
    try:
        await db.commit()
        await db.refresh(new_profile)
        new_profile.avatar = await s3_client.get_file_url(new_profile.avatar)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return new_profile
