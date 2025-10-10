from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date

from database import get_db
from config.dependencies import (
    get_jwt_auth_manager,
    get_s3_storage_client,
    get_token,
    get_settings
)
from config.settings import BaseAppSettings
from database.models.accounts import UserModel, UserProfileModel, UserGroupEnum
from schemas.profiles import ProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from exceptions.storage import S3FileUploadError, BaseS3Error
from validation.profile import (
    validate_name,
    validate_gender,
    validate_birth_date
)

router = APIRouter(prefix="/users", tags=["profiles"])


@router.post(
    "/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_user_profile(
        user_id: int,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    """
    Create a user profile.

    Args:
        user_id: ID of the user for whom to create the profile
        first_name: User's first name
        last_name: User's last name
        gender: User's gender
        date_of_birth: User's date of birth
        info: Additional information about the user
        avatar: Avatar image file
        db: Database session
        token: JWT authentication token
        jwt_manager: JWT manager for token validation
        s3_client: S3 storage client for avatar upload
        settings: Application settings

    Returns:
        ProfileResponseSchema: Created profile data

    Raises:
        HTTPException: Various errors based on validation and authorization
    """

    try:
        first_name = validate_name(first_name)
        last_name = validate_name(last_name)
        gender = validate_gender(gender)
        date_of_birth = validate_birth_date(date_of_birth)

        if not info or not info.strip():
            raise ValueError("Info cannot be empty or contain only spaces")
        info = info.strip()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
        current_user_group = payload.get("group")

        if not current_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired."
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    if current_user_id != user_id and current_user_group != UserGroupEnum.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    result = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    existing_profile = result.scalar_one_or_none()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        avatar_content = await avatar.read()

        max_size = 1 * 1024 * 1024
        if len(avatar_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Avatar file size must not exceed 1MB"
            )

        allowed_types = ["image/jpeg", "image/jpg", "image/png"]
        if avatar.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Avatar must be a JPG, JPEG, or PNG image"
            )

        file_extension = avatar.filename.split('.')[-1] if avatar.filename else "jpg"

        filename = f"avatars/{user_id}_avatar.{file_extension}"

        await s3_client.upload_file(
            file_data=avatar_content,
            object_name=filename
        )

        avatar_url = await s3_client.get_file_url(filename)

    except HTTPException:
        raise
    except (S3FileUploadError, BaseS3Error):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower(),
        last_name=last_name.lower(),
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar_url
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
        avatar=new_profile.avatar
    )
