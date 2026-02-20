from datetime import date

from fastapi import APIRouter, HTTPException, Header
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from database import get_db, UserModel, UserProfileModel, UserGroupModel, RefreshTokenModel
from schemas.profiles import ProfileResponseSchema, profile
from sqlalchemy.orm import selectinload

from storages.interfaces import S3StorageInterface

from config.dependencies import get_s3_storage_client

from database.models.accounts import GenderEnum, UserGroupEnum

from exceptions.security import TokenExpiredError, InvalidTokenError

from config import get_jwt_auth_manager
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()


async def save_avatar(file, s3_client, user_id) -> str:
    file_data = await file.read()

    extension = file.filename.split(".")[-1].lower()
    if extension == "jpeg":
        extension = "jpg"

    avatar_key = f"avatars/{user_id}_avatar.{extension}"

    await s3_client.upload_file(avatar_key, file_data)

    return avatar_key


async def verify_token(authorization: str | None = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'")

    token = parts[1]

    return token


async def get_current_user_id(token: str = Depends(verify_token),
                              jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)):
    try:
        payload = jwt_manager.decode_access_token(token)
        return payload["user_id"]
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=201)
async def user_profile(
        user_id: int,
        user: dict = Depends(profile),
        db: AsyncSession = Depends(get_db),
        current_user_id: int = Depends(get_current_user_id),
        token: str = Depends(verify_token),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    result = await db.execute(
        select(UserModel).options(
            selectinload(UserModel.profile),
            selectinload(UserModel.group)).where(UserModel.id == user_id)
    )
    user_db = result.scalar_one_or_none()

    current_user = await db.scalar(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )

    if not user_db or not user_db.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if current_user.group.name != UserGroupEnum.ADMIN and current_user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    if user_db.profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    try:
        avatar_key = await save_avatar(user["avatar"], s3_client, user_id)
    except Exception as e:
        import logging
        logging.error(f"Avatar upload failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        first_name=user["first_name"].lower(),
        last_name=user["last_name"].lower(),
        avatar=avatar_key,
        gender=user["gender"],
        date_of_birth=user["date_of_birth"],
        info=user["info"],
        user_id=user_id
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3_client.get_file_url(avatar_key)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )
