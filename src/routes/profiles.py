from copy import copy

from fastapi import HTTPException
from sqlalchemy import select
from src.exceptions.storage import BaseS3Error
from fastapi import APIRouter, Depends, Form
from fastapi.security import OAuth2PasswordBearer
from starlette import status
from schemas.profile import ProfileResponseSchema, ProfileCreateSchema
from typing import Annotated, cast
from sqlalchemy.ext.asyncio import AsyncSession
from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)
from fastapi import Request
from sqlalchemy.orm import joinedload
from src.database.models.accounts import UserModel, UserGroupEnum, UserProfileModel
from src.exceptions.security import TokenExpiredError
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface
from src.storages.interfaces import S3StorageInterface

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter(prefix="/users")


@router.post("/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
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

    stmt = select(UserModel).filter(id=user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active"
        )

    jwt_user_id = decoded_token.get("user_id")
    stmt = select(UserModel).filter_by(id=jwt_user_id).options(joinedload(UserModel.group))
    result = await db.execute(stmt)
    jwt_user = result.scalars().first()
    if user.id != jwt_user_id and jwt_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this operation."
        )

    stmt = select(UserProfileModel).filter_by(user_id=user_id)
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
    user_profile_data["user_id"] = cast(int, user.id)
    user_profile = UserProfileModel(**user_profile_data)
    db.add(user_profile)
    await db.commit()
    return user_profile
