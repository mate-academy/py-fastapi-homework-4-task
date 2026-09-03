from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    S3ConnectionError,
    S3FileUploadError
)
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from security.http import get_token
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=201)
async def create_profile(
        user_id: int,
        profile_data: Annotated[ProfileRequestSchema, Form()],
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        jwt_manager.verify_access_token_or_raise(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")

    token_record = jwt_manager.decode_access_token(token)
    user: UserModel | None = await db.scalar(
        select(UserModel)
        .options(
            joinedload(UserModel.group),
            joinedload(UserModel.profile)
        )
        .where(UserModel.id == token_record["user_id"])
    )

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")
    if user_id != token_record["user_id"] and user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=403, detail="You don't have permission to edit this profile."
        )
    if user.profile is not None:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    filename = f"avatars/{user_id}_avatar.jpg"
    contents = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(file_name=filename, file_data=contents)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(
            status_code=500, detail="Failed to upload avatar. Please try again later."
        )

    avatar_url = await s3_client.get_file_url(file_name=filename)
    fields = profile_data.model_dump(exclude={"avatar"})
    profile = UserProfileModel(**fields, user_id=user_id, avatar=filename)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return ProfileResponseSchema(
        **fields,
        id=profile.id,
        user_id=profile.user_id,
        avatar=avatar_url
    )
