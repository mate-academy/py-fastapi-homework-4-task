from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import joinedload, selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import TokenExpiredError
from security.http import get_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db, UserProfileModel
from database import UserModel
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from security.token_manager import JWTAuthManager
from storages import S3StorageClient
from validation.profile import (
    info_validator,
    validate_birth_date,
    validate_image,
    validate_gender,
    validate_name,
)

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    user: ProfileRequestSchema = Depends(ProfileRequestSchema.form),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
    s3_client: S3StorageClient = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserModel)
        .where(UserModel.id == user_id)
        .options(selectinload(UserModel.profile), selectinload(UserModel.group))
    )
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()

    try:
        validate_name(user.first_name)
        validate_name(user.last_name)
        validate_birth_date(user.date_of_birth)
        info_validator(user.info)
        validate_image(user.avatar)
    except (ValidationError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )

    try:
        user_token = jwt_manager.decode_access_token(token)

    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )
    stmt_request_user = (
        select(UserModel)
        .where(UserModel.id == user_token["user_id"])
        .options(selectinload(UserModel.group))
    )
    result = await db.execute(stmt_request_user)
    request_user = result.scalar_one_or_none()

    if db_user is None or db_user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if user_token["user_id"] != user_id and request_user.group_id != 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    if db_user.profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )
    try:
        filename = f"avatars/{user_id}_avatar.jpg"

        content = await user.avatar.read()

        await s3_client.upload_file(filename, content)
        url_file = await s3_client.get_file_url(filename)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )
    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=user.first_name.lower(),
        last_name=user.last_name.lower(),
        gender=user.gender,
        date_of_birth=user.date_of_birth,
        info=user.info,
        avatar=filename,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    new_profile.avatar = url_file
    return new_profile
