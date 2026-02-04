from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from database.models.accounts import GenderEnum
from config import get_jwt_auth_manager, get_s3_storage_client
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from security.http import get_token
from exceptions import BaseSecurityError
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from validation import validate_image

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    description="Create a new profile for a user, including an avatar upload.",
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
        user_id: int,
        profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
        avatar: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    """
    Endpoint for creating a user profile.

    This endpoint validates the user's token, checks for authorization,
    ensures the user doesn't already have a profile, uploads an avatar to S3,
    and saves the profile details to the database.
    """
    # 1. Token validation
    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired." if "expired" in str(e).lower() else str(e)
        )

    # 2. Authorization rules
    stmt = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == current_user_id)
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if current_user_id != user_id and current_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    # 3. User existence and status
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalars().first()
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    # 4. Check for existing profile
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # 5. Avatar upload to s3 storage
    try:
        validate_image(avatar)
        ext = avatar.filename.split(".")[-1]
        object_key = f"avatars/{user_id}_avatar.{ext}"

        content = await avatar.read()
        await s3_client.upload_file(object_key, content)
        avatar_url = await s3_client.get_file_url(object_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # 6. Profile creation and storage
    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=profile_data.first_name.lower(),
            last_name=profile_data.last_name.lower(),
            gender=GenderEnum(profile_data.gender),
            date_of_birth=profile_data.date_of_birth,
            info=profile_data.info,
            avatar=object_key
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the profile."
        )

    response_data = ProfileResponseSchema.model_validate(new_profile)
    response_data.avatar = avatar_url
    return response_data
