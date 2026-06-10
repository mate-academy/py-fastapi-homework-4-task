from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from database.models.accounts import GenderEnum
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    token: str = Depends(get_token),
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    try:
        decoded_token = jwt_manager.decode_access_token(token)
        current_user_id = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    current_user = await db.execute(
        select(UserModel).options(joinedload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )
    current_user = current_user.scalars().first()

    target_user = await db.execute(
        select(UserModel).options(joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    target_user = target_user.scalars().first()

    if (
        not current_user
        or not target_user
        or not current_user.is_active
        or not target_user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    is_owner = current_user_id == user_id
    is_admin = current_user.has_group(UserGroupEnum.ADMIN)

    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )
    if target_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_bytes = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(avatar_key, avatar_bytes)
    except BaseS3Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        ) from error

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=GenderEnum(profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    avatar_url = await s3_client.get_file_url(avatar_key)
    gender = (
        new_profile.gender.value
        if isinstance(new_profile.gender, GenderEnum)
        else new_profile.gender
    )

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url,
    )
