from sqlalchemy import select

from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import (
    get_db, UserModel,
    UserGroupEnum,
    UserProfileModel
)
from exceptions import (
    BaseSecurityError,
    S3ConnectionError,
    S3FileUploadError
)
from schemas.profiles import (
    ProfileResponseSchema,
    ProfileCreateRequestSchema
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    description="Create a profile for a user, including avatar upload to s3 storage.",
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
        user_id: int,
        profile_data: ProfileCreateRequestSchema = Depends(ProfileCreateRequestSchema.as_form),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )
    token_user_id = payload.get("user_id")

    if token_user_id != user_id:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.group))
            .filter_by(id=token_user_id)
        )
        result = await db.execute(stmt)
        requesting_user = result.scalars().first()

        if not requesting_user or not requesting_user.has_group(
                UserGroupEnum.ADMIN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    stmt = select(UserModel).filter_by(id=user_id)
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == target_user.id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_bytes = await profile_data.avatar.read()
    avatar_key = f"avatars/{user_id}_avatar.jpg"

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    avatar_url = await s3_client.get_file_url(avatar_key)

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url,
    )
