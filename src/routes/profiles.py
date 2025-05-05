from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupModel, UserGroupEnum
from exceptions import TokenExpiredError, S3ConnectionError, S3FileUploadError

from schemas.profiles import (
    UserProfileCreateRequestSchema,
    UserProfileCreateResponseSchema,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=UserProfileCreateResponseSchema,
    status_code=201,
)
async def create_profile(
    user_id: int,
    token: str = Depends(get_token),
    user_data: UserProfileCreateRequestSchema = Form(),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")

    user_id_from_token = decoded_token.get("user_id")

    stmt = await db.execute(
        select(UserModel)
        .where(UserModel.id == user_id_from_token)
        .options(selectinload(UserModel.group))
    )
    user = stmt.scalars().first()
    if user.group.name != UserGroupEnum.ADMIN and user_id != user_id_from_token:
        raise HTTPException(
            status_code=403, detail="You don't have permission to edit this profile."
        )

    stmt = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user_record = stmt.scalars().first()
    if (user_record is None) or (user_record.is_active is False):
        raise HTTPException(status_code=401, detail="User not found or not active.")

    stmt = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    user_profile_record = stmt.scalars().first()
    if user_profile_record:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    file_bytes = await user_data.avatar.read()
    file_name = f"avatars/{user_id}_avatar.jpg"
    try:
        await s3_client.upload_file(file_name, file_bytes)
    except S3ConnectionError:
        raise HTTPException(
            status_code=500, detail="Failed to upload avatar. Please try again later."
        )
    except S3FileUploadError:
        raise HTTPException(
            status_code=500, detail="Failed to upload avatar. Please try again later."
        )

    user_profile_data = {
        "user_id": user_id,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "gender": user_data.gender,
        "date_of_birth": user_data.date_of_birth,
        "info": user_data.info,
        "avatar": file_name,
    }

    profile = UserProfileModel(**user_profile_data)
    db.add(profile)
    await db.flush()
    await db.commit()

    response_data = {
        "id": profile.id,
        **user_profile_data,
    }
    return UserProfileCreateResponseSchema(**response_data)
