import pdb

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from database import get_db
from config.dependencies import get_jwt_auth_manager, get_s3_storage_client, get_token, get_settings
from config.settings import BaseAppSettings
from database.models.accounts import UserModel, UserProfileModel
from schemas.profiles import ProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from exceptions.storage import S3FileUploadError, BaseS3Error

from validation.profile import validate_name

from validation.profile import validate_gender, validate_birth_date

from validation.profile import validate_image

from exceptions.security import TokenExpiredError

router = APIRouter(prefix="/users", tags=["profiles"])


# ----------------- Validation Functions -----------------
async def validate_profile_fields(first_name: str, last_name: str, gender: str, dob: date, info: str):
    try:
        validate_name(first_name)
        v_first_name = first_name

        validate_name(last_name)
        v_last_name = last_name

        validate_gender(gender)
        v_gender = gender

        validate_birth_date(dob)
        v_dob = dob

        if not info or not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        v_info = info.strip()
        return v_first_name, v_last_name, v_gender, v_dob, v_info
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


async def validate_avatar_file(avatar: UploadFile):
    try:
        validate_image(avatar=avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid image format"
        )


# ----------------- User Functions -----------------
async def decode_token(token: str, jwt_manager: JWTAuthManagerInterface):

    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid or user_id missing."
            )
        return user_id
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )


async def get_user_by_id(db: AsyncSession, user_id: int):
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found or not active.")
    return user


async def check_permissions(current_user_id: int, target_user: UserModel, requested_user_id: int):
    is_admin = target_user.group_id == 3
    if current_user_id != requested_user_id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You don't have permission to edit this profile.")


async def check_existing_profile(db: AsyncSession, user_id: int):
    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")


# ----------------- Storage Functions -----------------
async def upload_avatar_to_s3(s3_client: S3StorageInterface, content: bytes, user_id: int):
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


# ----------------- Endpoint -----------------
@router.post("/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
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
    (validated_first_name, validated_last_name,
     validated_gender, validated_dob, validated_info) = await validate_profile_fields(
        first_name, last_name, gender, date_of_birth, info
    )

    avatar_content = await validate_avatar_file(avatar)
    current_user_id = await decode_token(token, jwt_manager)
    current_user = await get_user_by_id(db, current_user_id)
    await check_permissions(current_user_id, current_user, user_id)
    await check_existing_profile(db, user_id)
    avatar_key = await upload_avatar_to_s3(s3_client, avatar_content, user_id)

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
