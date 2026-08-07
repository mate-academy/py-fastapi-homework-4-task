from fastapi import APIRouter, HTTPException, Depends, status, UploadFile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db
from database.models.accounts import UserModel, UserProfileModel
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from config.dependencies import (
    get_jwt_auth_manager,
    get_s3_storage_client
)
from exceptions.security import TokenExpiredError
from exceptions.storage import BaseS3Error

from schemas.profiles import (
    ProfileResponseSchema,
    ProfileRequestFormSchema
)
from security.http import get_token


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProfileResponseSchema
)
async def create_profile(
    user_id: int,
    data: ProfileRequestFormSchema = Depends(ProfileRequestFormSchema.as_form),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileResponseSchema:
    try:
        decode_data = jwt_auth_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    current_user_result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == decode_data["user_id"])
    )
    current_user: UserModel = current_user_result.scalar_one()

    if current_user.group.name != "admin" and user_id != decode_data["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    user_result = await db.execute(
        select(UserModel)
        .where(UserModel.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    profile_result = await db.execute(
        select(UserProfileModel)
        .where(UserProfileModel.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()

    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    profile_data = data.model_dump()
    avatar: UploadFile = profile_data.pop("avatar")

    file_name = f"avatars/{user_id}_{avatar.filename}"

    profile = UserProfileModel(**profile_data, user_id=user_id)

    try:
        await s3_client.upload_file(file_name, await avatar.read())
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    profile.avatar = file_name

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=await s3_client.get_file_url(file_name)
    )
