from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserGroupEnum, UserGroupModel, UserModel, UserProfileModel, get_db
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    user_id: int,
    profile_data: Annotated[ProfileCreateSchema, Form()],
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        token_user_id = jwt_manager.decode_access_token(token).get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))

    if token_user_id != user_id:
        group = await db.scalar(select(UserGroupModel.name).join(UserModel).where(UserModel.id == token_user_id))
        if group in (None, UserGroupEnum.USER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    user = await db.get(UserModel, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    if await db.scalar(select(UserProfileModel.id).where(UserProfileModel.user_id == user_id)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    avatar_key = f"avatars/{user_id}_{profile_data.avatar.filename}"
    try:
        await s3_client.upload_file(avatar_key, await profile_data.avatar.read())
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile_fields = profile_data.model_dump(exclude={"avatar"})
    profile = UserProfileModel(user_id=user_id, avatar=avatar_key, **profile_fields)
    db.add(profile)
    await db.commit()

    return ProfileResponseSchema(
        id=profile.id,
        user_id=user_id,
        avatar=await s3_client.get_file_url(avatar_key),
        **profile_fields,
    )
