from datetime import datetime, date

from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, Form, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import S3FileUploadError
from schemas import ProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token
from storages import S3StorageInterface
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

router = APIRouter()


async def get_authenticated_user_id(token: str, jwt_manager: JWTAuthManagerInterface) -> int:
    """Decode token and extract user_id."""
    try:
        decoded_token = jwt_manager.decode_access_token(token)
        return decoded_token.get("user_id")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )


async def validate_user_exists_and_active(user_id: int, db: AsyncSession) -> UserModel:
    """Check if user exists and is active."""
    stmt = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )
    return user


async def check_authorization(
    authenticated_user_id: int,
    target_user_id: int,
    db: AsyncSession
) -> UserModel:
    """Check if user has permission to create profile."""
    if authenticated_user_id == target_user_id:
        stmt = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == authenticated_user_id)
        result = await db.execute(stmt)
        return result.scalars().first()
    else:
        stmt = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == authenticated_user_id)
        result = await db.execute(stmt)
        authenticated_user = result.scalars().first()

        if not authenticated_user.has_group(UserGroupEnum.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )
        return authenticated_user


async def check_profile_not_exists(user_id: int, db: AsyncSession) -> None:
    """Check if user already has a profile."""
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )


def validate_name_field(name: str, field_name: str) -> None:
    """Validate a name field."""
    try:
        validate_name(name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


def validate_birth_date_from_string(date_of_birth: str) -> date:
    """Parse and validate birth date from string."""
    birth_date = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    try:
        validate_birth_date(birth_date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    return birth_date


def validate_info_field(info: str) -> None:
    """Validate info field is not empty."""
    if not info or info.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Info field cannot be empty or contain only spaces."
        )


def validate_gender_field(gender: str) -> None:
    """Validate gender field."""
    try:
        validate_gender(gender)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


def validate_avatar_field(avatar: UploadFile) -> None:
    """Validate avatar file."""
    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


def validate_profile_data(
    first_name: str,
    last_name: str,
    gender: str,
    date_of_birth: str,
    info: str,
    avatar: UploadFile
) -> date:
    """Validate all profile data fields."""
    validate_name_field(first_name, "first_name")
    validate_name_field(last_name, "last_name")
    validate_gender_field(gender)
    birth_date = validate_birth_date_from_string(date_of_birth)
    validate_info_field(info)
    validate_avatar_field(avatar)
    return birth_date


async def upload_avatar_to_s3(
    user_id: int,
    avatar: UploadFile,
    s3_client: S3StorageInterface
) -> str:
    """Upload avatar to S3 and return the URL."""
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_data = await avatar.read()

    try:
        await s3_client.upload_file(avatar_key, avatar_data)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    return await s3_client.get_file_url(avatar_key)


async def create_profile_in_db(
    user_id: int,
    first_name: str,
    last_name: str,
    gender: str,
    birth_date: date,
    info: str,
    avatar_key: str,
    db: AsyncSession
) -> UserProfileModel:
    """Create profile in database."""
    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower(),
        last_name=last_name.lower(),
        gender=gender,
        date_of_birth=birth_date,
        info=info,
        avatar=avatar_key
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return new_profile


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_user_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileResponseSchema:
    authenticated_user_id = await get_authenticated_user_id(token, jwt_manager)
    await validate_user_exists_and_active(user_id, db)
    await check_authorization(authenticated_user_id, user_id, db)
    await check_profile_not_exists(user_id, db)

    birth_date = validate_profile_data(first_name, last_name, gender, date_of_birth, info, avatar)
    avatar_url = await upload_avatar_to_s3(user_id, avatar, s3_client)
    avatar_key = f"avatars/{user_id}_avatar.jpg"

    new_profile = await create_profile_in_db(
        user_id, first_name, last_name, gender, birth_date, info, avatar_key, db
    )

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url
    )
