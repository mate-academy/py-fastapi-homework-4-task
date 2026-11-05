import datetime

from fastapi import HTTPException

from fastapi import APIRouter
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import schemas
from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel
from database.models.accounts import TokenBaseModel, UserGroupEnum, UserProfileModel
from exceptions import BaseSecurityError
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=schemas.profiles.ProfileResponseSchema, status_code=201)
async def profile_create(user_id: int,
                         profile: schemas.profiles.ProfileRequestSchema = Depends(
                             schemas.profiles.ProfileRequestSchema.from_form),
                         db: AsyncSession = Depends(get_db),
                         token_req: str = Depends(get_token),
                         s3_client: S3StorageInterface = Depends(get_s3_storage_client),
                         jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
                         ):
    try:
        payload = jwt_manager.decode_access_token(token_req)
    except BaseSecurityError as error:
        raise HTTPException(status_code=401, detail=str(error))

    token_user_id = payload["user_id"]

    obj_user = await db.scalar(
        select(UserModel).options(
            selectinload(UserModel.group), selectinload(
                UserModel.profile)).where(
            UserModel.id == token_user_id))
    is_admin = obj_user is not None and obj_user.group.name in (UserGroupEnum.ADMIN, UserGroupEnum.MODERATOR)
    if token_user_id != user_id and not is_admin:
        raise HTTPException(403, "You don't have permission to edit this profile.")

    obj_user = await db.scalar(
        select(UserModel)
        .options(selectinload(UserModel.profile))
        .where(UserModel.id == user_id)
    )

    if obj_user is None or not obj_user.is_active:
        raise HTTPException(401, "User not found or not active.")

    if obj_user.profile is not None:
        raise HTTPException(400, "User already has a profile.")

    try:
        filepath = f"avatars/{user_id}_avatar.jpg"
        await s3_client.upload_file(filepath, await profile.avatar.read())
    except Exception:
        raise HTTPException(500, "Failed to upload avatar. Please try again later.")

    result = UserProfileModel(
        user_id=user_id,
        first_name=profile.first_name.lower(),
        last_name=profile.last_name.lower(),
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=filepath
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    full_url = await s3_client.get_file_url(filepath)
    return {
        "id": result.id,
        "user_id": result.user_id,
        "first_name": result.first_name,
        "last_name": result.last_name,
        "gender": result.gender,
        "date_of_birth": result.date_of_birth,
        "info": result.info,
        "avatar": full_url
    }
