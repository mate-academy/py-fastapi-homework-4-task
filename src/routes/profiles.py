from datetime import datetime, timezone, date

from fastapi import Depends, HTTPException, status, APIRouter, Form, UploadFile, File
from sqlalchemy import cast, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, UserModel, UserProfileModel, UserGroupModel, UserGroupEnum
from config import get_s3_storage_client, get_jwt_auth_manager
from exceptions import BaseSecurityError
from schemas.profiles import ProfileResponseSchema, ProfileCreateRequestSchema
from storages.interfaces import S3StorageInterface
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token

import schemas

router = APIRouter()

# Write your code here


@router.post("/users/{user_id}/profile/", status_code=status.HTTP_201_CREATED)
async def user_profile_creation(
        user_id: int,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileResponseSchema:

    profile_validation = ProfileCreateRequestSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar
    )

    try:

        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    request = await db.execute(
        select(UserModel).filter_by(id=current_user_id)
    )
    db_current_user = request.scalar_one_or_none()

    if not db_current_user or not db_current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or token."
        )

    stmt = select(
        UserGroupModel.id
    ).where(UserGroupModel.name == UserGroupEnum.ADMIN)
    db_group_admin_id = await db.scalar(stmt)

    if current_user_id != user_id and db_current_user.group_id != db_group_admin_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile."
        )

    request = await db.execute(select(UserModel).filter_by(id=user_id))

    db_user = request.scalar_one_or_none()
    if not db_user or not db_user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    request = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == db_user.id)
    )

    db_user_profile = request.scalar_one_or_none()

    if db_user_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    try:
        avatar_url = await s3_client.upload(avatar)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )

        # БЛОК 2: Пишем в БД (если Блок 1 прошел успешно)
    db_user_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_validation.first_name,
        last_name=profile_validation.last_name,
        gender=profile_validation.gender,
        date_of_birth=profile_validation.date_of_birth,
        info=profile_validation.info,
        avatar=avatar_url

    )
    db.add(db_user_profile)
    await db.commit()
    await db.refresh(db_user_profile)

    return ProfileResponseSchema.model_validate(db_user_profile)
