import pdb

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
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

from schemas.profiles import ProfileCreateSchema

router = APIRouter(prefix="/users", tags=["profiles"])


@router.post(
    "/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_user_profile(
        user_id: int, first_name: str = Form(...), last_name: str = Form(...),
        gender: str = Form(...), date_of_birth: date = Form(...),
        info: str = Form(...), avatar: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        settings: BaseAppSettings = Depends(get_settings)
):
    """Create a user profile."""

    async def validate_fields():
        try:
            v_first_name = ProfileCreateSchema.validate_first_name(first_name)
            v_last_name = ProfileCreateSchema.validate_last_name(last_name)
            v_gender = ProfileCreateSchema.validate_gender_field(gender)
            v_dob = ProfileCreateSchema.validate_date_of_birth_field(date_of_birth)
            if not info or not info.strip():
                raise ValueError("Info field cannot be empty or contain only spaces.")
            v_info = info.strip()
            return v_first_name, v_last_name, v_gender, v_dob, v_info
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    async def validate_avatar_file():
        try:
            content = await avatar.read()
            max_size = getattr(settings, "MAX_AVATAR_SIZE_MB", 1) * 1024 * 1024
            if len(content) > max_size:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    detail="Image size exceeds 1 MB")
            if avatar.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    detail="Invalid image format. Avatar must be JPG, JPEG, or PNG")
            return content
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="An unexpected error occurred during file processing.")

    async def decode_token():
        try:
            payload = jwt_manager.decode_access_token(token)
            current_id = payload.get("user_id")
            if current_id is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Token is invalid or user_id missing.")
            return current_id
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    async def get_user(user_id: int):
        result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="User not found or not active.")
        return user

    async def check_permissions(current_id: int, target_user: UserModel):
        is_admin = target_user.group_id == 3
        if current_id != user_id and not is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You don't have permission to edit this profile.")

    async def check_existing_profile():
        result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    async def upload_avatar(content: bytes):
        try:
            filename = f"avatars/{user_id}_avatar.jpg"
            await s3_client.upload_file(file_data=content, file_name=filename)
            return filename
        except (S3FileUploadError, BaseS3Error):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to upload avatar. Please try again later.")
        except Exception:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="An unexpected error occurred during file processing.")

    # === MAIN FLOW ===
    (validated_first_name, validated_last_name,
     validated_gender, validated_dob, validated_info) = await validate_fields()
    avatar_content = await validate_avatar_file()
    current_user_id = await decode_token()
    current_user = await get_user(current_user_id)
    await check_permissions(current_user_id, current_user)
    await check_existing_profile()
    avatar_key = await upload_avatar(avatar_content)

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=validated_first_name.lower(),
        last_name=validated_last_name.lower(),
        gender=validated_gender,
        date_of_birth=validated_dob,
        info=validated_info,
        avatar=avatar_key
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    final_avatar_url = await s3_client.get_file_url(new_profile.avatar)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth.strftime("%Y-%m-%d"),
        info=new_profile.info,
        avatar=final_avatar_url,
    )
