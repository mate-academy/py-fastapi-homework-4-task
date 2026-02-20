from copy import copy
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.requests import Request

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, get_db, UserGroupEnum, UserProfileModel
from exceptions import TokenExpiredError, BaseS3Error
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    user_id: int,
    request: Request,
    data: Annotated[ProfileCreateSchema, Form()],
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    token = get_token(request)
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    stmt = select(UserModel).filter_by(id=user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    jwt_user_id = decoded_token.get("user_id")
    stmt = select(UserModel).filter_by(id=jwt_user_id).options(joinedload(UserModel.group))
    result = await db.execute(stmt)
    jwt_user = result.scalars().first()
    if user.id != jwt_user_id and jwt_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    stmt = select(UserProfileModel).filter_by(id=user_id)
    result = await db.execute(stmt)
    if bool(result.scalars().first()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )
    try:
        content = await data.avatar.read()
        await s3_client.upload_file(file_name=f"avatars/{user_id}_avatar.jpg", file_data=content)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
    user_profile_data = copy(data.model_dump())
    user_profile_data["avatar"] = await s3_client.get_file_url(f"avatars/{user_id}_avatar.jpg")
    user_profile_data["user"] = user
    user_profile_data["user_id"] = cast(int, user.id),
    user_profile = UserProfileModel(**user_profile_data)
    db.add(user_profile)
    await db.commit()
    return user_profile
