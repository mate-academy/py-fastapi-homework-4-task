from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import HttpUrl

from database import get_db
from database.models.accounts import (UserProfileModel,
                                      UserGroupEnum,
                                      UserGroupModel,
                                      UserModel,
                                      GenderEnum)
from schemas.profiles import (ProfileCreateShema,
                              ProfileResponseShema)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from config import get_jwt_auth_manager, get_s3_storage_client
from storages import S3StorageInterface
from exceptions import BaseSecurityError, S3FileUploadError


router = APIRouter()


@router.post(
    "users/{user_id}/profile",
    response_model=ProfileResponseShema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    profile_data: ProfileCreateShema = Depends(ProfileCreateShema.from_form)
) -> ProfileResponseShema:
    try:
        payload = jwt_manager.create_access_token(token=token)
        token_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    if token_user_id != user_id:
        stmt = (
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == token_user_id)
        )
        result = await db.execute(stmt)
        user_group = result.scalars().first()
        if not user_group or user_group.name != UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )
        stmt_profile = (select(UserProfileModel)
                        .where(UserProfileModel.user_id == user_id))
        result_profile = await db.execute(stmt_profile)
        existing_profile = result_profile.scalars().first()
        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a profile."
            )
        avatar_bytes = await profile_data.avatar.read()
        avatar_key = f"avatars/{user_id}_{profile_data.avatar.filename}"
        try:
            await s3_client.upload_file(file_name=avatar_key,
                                        file_data=avatar_bytes)
        except S3FileUploadError as e:
            print(f"Error uploading avatar to S3: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later."
            )
        new_profile = UserProfileModel(
            user_id=cast(int, user_id),
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            gender=cast(GenderEnum, profile_data.gender),
            date_of_birth=profile_data.date_of_birth,
            avatar=avatar_key
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        avatar_url = await s3_client.get_file_url(new_profile.avatar)
        return ProfileResponseShema(
            id=new_profile.id,
            user_id=new_profile.user_id,
            first_name=new_profile.first_name,
            last_name=new_profile.last_name,
            gender=new_profile.gender,
            date_of_birth=new_profile.date_of_birth,
            info=new_profile.info,
            avatar=cast(HttpUrl, avatar_url)
        )
