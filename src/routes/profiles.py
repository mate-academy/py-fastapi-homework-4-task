from fastapi import APIRouter, Header, HTTPException
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from exceptions import TokenExpiredError, S3FileUploadError
from schemas.profiles import ProfileModel
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def get_current_user(
    authorization: str | None = Header(default=None),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is missing",
        )

    parts = authorization.split()

    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    token = parts[1]

    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired.",
        )

    user_id = decoded_token.get("user_id")

    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active.",
        )

    return user


@router.post("/users/{user_id}/profile/", status_code=201)
async def create_profile(
    user_id: int,
    profile_data: ProfileModel = Depends(ProfileModel.as_form),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    s3_storage: S3StorageInterface = Depends(get_s3_storage_client),
):
    if current_user.id != user_id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile.",
        )

    result = await db.execute(select(UserModel).where(UserModel.id == user_id))

    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active.",
        )

    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )

    profile = result.scalar_one_or_none()

    if profile is not None:
        raise HTTPException(
            status_code=400,
            detail="User already has a profile.",
        )

    file_data = await profile_data.avatar.read()

    avatar_key = f"avatars/{user_id}_avatar.jpg"

    try:
        await s3_storage.upload_file(
            avatar_key,
            file_data,
        )
    except S3FileUploadError:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
        user_id=user_id,
    )

    db.add(new_profile)

    await db.commit()
    await db.refresh(new_profile)

    avatar_url = await s3_storage.get_file_url(avatar_key)

    return {
        "id": new_profile.id,
        "first_name": new_profile.first_name,
        "last_name": new_profile.last_name,
        "gender": new_profile.gender,
        "date_of_birth": new_profile.date_of_birth,
        "info": new_profile.info,
        "avatar": avatar_url,
        "user_id": new_profile.user_id,
    }
