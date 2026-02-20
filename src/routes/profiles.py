from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, UserProfileModel, get_db
from database.models.accounts import GenderEnum, UserGroupEnum
from exceptions import S3FileUploadError, TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def get_current_user(
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
) -> UserModel:
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    user_id = decoded_token.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token is invalid")
    user = await db.execute(select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == user_id))
    user = user.scalar_one_or_none()
    if user:
        return user
    else:
        raise HTTPException(status_code=401, detail="User not found or not active.")


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=201)
async def user_profile_creation(
        user_id: int,
        profile_data: Annotated[ProfileRequestSchema, Depends(ProfileRequestSchema.as_form)],
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    if current_user.id != user_id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")
    result = await db.execute(select(UserModel).options(joinedload(UserModel.profile)).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")
    if user.profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")
    if profile_data.gender.lower() == "man":
        gender = GenderEnum.MAN
    else:
        gender = GenderEnum.WOMAN

    try:
        avatar_byte_data = await profile_data.avatar.read()
        avatar_path = f"avatars/{user_id}_{profile_data.avatar.filename}"
        await s3_client.upload_file(file_name=avatar_path, file_data=avatar_byte_data)
    except S3FileUploadError:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        user_id=user_id,
        avatar=avatar_path
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    avatar_url = await s3_client.get_file_url(profile.avatar)

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "gender": profile.gender,
        "date_of_birth": profile.date_of_birth,
        "info": profile.info,
        "avatar": avatar_url
    }
