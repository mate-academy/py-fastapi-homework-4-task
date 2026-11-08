from datetime import datetime

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
    # Decode token and get authenticated user_id
    try:
        decoded_token = jwt_manager.decode_access_token(token)
        authenticated_user_id = decoded_token.get("user_id")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    # Check if the user exists and is active
    stmt = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    # Check authorization: user can only create their own profile unless they are admin
    if authenticated_user_id == user_id:
        authenticated_user = target_user
    else:
        # Get authenticated user to check if they are admin
        stmt_auth = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == authenticated_user_id)
        result_auth = await db.execute(stmt_auth)
        authenticated_user = result_auth.scalars().first()

        if not authenticated_user.has_group(UserGroupEnum.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    # Check if profile already exists
    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result_profile = await db.execute(stmt_profile)
    existing_profile = result_profile.scalars().first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # Validate input data
    try:
        validate_name(first_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    try:
        validate_name(last_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    try:
        validate_gender(gender)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    birth_date = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    try:
        validate_birth_date(birth_date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    if not info or info.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Info field cannot be empty or contain only spaces."
        )

    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    # Upload avatar to S3
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_data = await avatar.read()

    try:
        await s3_client.upload_file(avatar_key, avatar_data)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Get avatar URL
    avatar_url = await s3_client.get_file_url(avatar_key)

    # Create profile in database
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
