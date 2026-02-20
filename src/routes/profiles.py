from fastapi import APIRouter, status, Depends, Request, HTTPException
from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import cast
from database import get_db
from database.models.accounts import UserModel, UserProfileModel, GenderEnum, UserGroupModel, UserGroupEnum
from security.http import get_token
from config import get_jwt_auth_manager, get_s3_storage_client
from schemas.profiles import UserProfileResponseSchema, UserProfileCreateSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

from exceptions.security import BaseSecurityError, TokenExpiredError

from exceptions import S3FileUploadError

router = APIRouter()


@router.post("/users/{user_id}/profile/",
             response_model=UserProfileResponseSchema,
             status_code=status.HTTP_201_CREATED)
async def create_user_profile(
        user_id: int,
        profile_data: UserProfileCreateSchema = Depends(UserProfileCreateSchema.from_form),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> UserProfileResponseSchema:
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    if user_id != token_user_id:
        stmt = (
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == token_user_id)
        )
        result = await db.execute(stmt)
        user_group = result.scalars().first()
        if not user_group or user_group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    stmt = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = stmt.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    existing_profile = result.scalar_one_or_none()
    if existing_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_data = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_data)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=cast(int, user.id),
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=cast(GenderEnum, profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    avatar_url = await s3_client.get_file_url(new_profile.avatar)

    return UserProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=cast(HttpUrl, avatar_url)
    )
