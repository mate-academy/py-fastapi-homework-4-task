from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, get_db, UserGroupEnum, UserProfileModel
from database.models.accounts import GenderEnum
from exceptions import TokenExpiredError, S3ConnectionError, S3FileUploadError
from schemas import UserProfileResponseSchema, UserProfileRequestSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", status_code=status.HTTP_201_CREATED)
async def create_user_profile(
        user_id: int,
        data: Annotated[UserProfileRequestSchema, Form()],
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        db: AsyncSession = Depends(get_db),
) -> UserProfileResponseSchema:
    try:
        decoded = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    request_user_stmt = (select(UserModel)
                         .options(selectinload(UserModel.group))
                         .where(UserModel.id == decoded["user_id"]))
    request_user = (await db.execute(request_user_stmt)).scalar_one_or_none()

    if user_id != decoded["user_id"] and not request_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You don't have permission to edit this profile.")

    profile_stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    profile = (await db.execute(profile_stmt)).scalar_one_or_none()
    if profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    file_name = f"avatars/{user_id}_avatar.jpg"
    file = await data.avatar.read()
    try:
        await s3_client.upload_file(file_name, file)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to upload avatar. Please try again later.")
    file_url = await s3_client.get_file_url(file_name)

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=data.first_name.lower(),
        last_name=data.last_name.lower(),
        avatar=file_name,
        gender=GenderEnum(data.gender),
        date_of_birth=data.date_of_birth,
        info=data.info,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    response = UserProfileResponseSchema.model_validate(new_profile)
    response = response.model_copy(update={"avatar": file_url})
    return response
