from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from config import get_s3_storage_client, get_jwt_auth_manager
from database import UserModel, UserProfileModel, UserGroupEnum, get_db
from exceptions import S3FileUploadError, BaseSecurityError
from database.models.accounts import GenderEnum
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from storages.interfaces import S3StorageInterface
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Profile",
)
async def create_profile(
        user_id: int,
        token: str = Depends(get_token),
        profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    current_user_id = payload.get("user_id")

    # Check permissions and current user existence
    stmt = select(UserModel).where(UserModel.id == current_user_id).options(joinedload(UserModel.group))
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if current_user_id != user_id and current_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    # Check target user existence and status
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    target_user = current_user if current_user_id == user_id else result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    # Check if profile already exists
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # Upload avatar to S3
    file_extension = profile_data.avatar.filename.split(".")[-1]
    avatar_filename = f"avatars/{user_id}_avatar.{file_extension}"
    try:
        avatar_data = await profile_data.avatar.read()
        await s3_client.upload_file(avatar_filename, avatar_data)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Create profile
    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=GenderEnum(profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_filename
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    # Generate full avatar URL for response
    avatar_url = await s3_client.get_file_url(avatar_filename)

    # Prepare response
    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender.value,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url
    )
