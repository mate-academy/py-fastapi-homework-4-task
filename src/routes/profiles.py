from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, UserModel, UserProfileModel
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions.security import TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from validation.profile import validate_image

router = APIRouter()


async def get_current_user(
    request: Request,
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db)
):
    token = get_token(
        request=request
    )
    try:
        token_data = jwt_manager.decode_access_token(token=token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token."
        )
    user_id = token_data.get("user_id")
    query = select(UserModel).options(
        joinedload(UserModel.group)
    ).where(UserModel.id == user_id)
    result = await db.execute(query)
    current_user = result.scalar_one_or_none()
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )
    return current_user


@router.post("/users/{user_id}/profile/", status_code=201)
async def profile_create(
    user_id: int,
    profile_data: Annotated[
        ProfileRequestSchema,
        Depends(ProfileRequestSchema.as_form)
    ],
    current_user: UserModel = Depends(get_current_user),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db)
) -> ProfileResponseSchema:
    query = select(UserModel).where(
        UserModel.id == user_id
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )
    if current_user.id != user_id and current_user.group.name != "admin":
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile."
        )
    user_profile = await db.execute(
        select(UserProfileModel).where(
            UserProfileModel.user_id == user_id
        )
    )
    if user_profile.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="User already has a profile."
        )
    file_name = f"avatars/{user_id}_{profile_data.avatar.filename}"
    file_data = await profile_data.avatar.read()
    try:
        await s3_client.upload_file(
            file_name=file_name,
            file_data=file_data
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )
    avatar_url = await s3_client.get_file_url(
        file_name=file_name
    )
    profile = UserProfileModel(
        user_id=user.id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=file_name
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return ProfileResponseSchema(
        id=profile.id,
        user_id=user.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )
