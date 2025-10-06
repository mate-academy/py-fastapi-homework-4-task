from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


from database import (
    get_db,
    UserModel,
    UserProfileModel,
)
from exceptions import S3FileUploadError
from schemas import ProfileResponseSchema

from storages import S3StorageInterface
from config import get_s3_storage_client

from .utils import get_current_user, get_avatar_presigned_url

from fastapi import UploadFile, File, Form
from typing import Optional
from datetime import date

# from database.models.accounts import GenderEnum


from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="User Profile Creation",
    description="Create user profile.",
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    date_of_birth: Optional[date] = Form(None),
    info: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    current_user_id: UserModel = Depends(get_current_user),
):

    try:
        if first_name:
            validate_name(first_name)
        if last_name:
            validate_name(last_name)
        if gender:
            validate_gender(gender)
        if date_of_birth:
            validate_birth_date(date_of_birth)
        if info is not None and not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        if avatar:
            validate_image(avatar)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    stmt_current = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )
    result_current = await db.execute(stmt_current)
    authenticated_user = result_current.scalars().first()

    stmt_target = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == user_id)
    )
    result_target = await db.execute(stmt_target)
    target_user = result_target.scalars().first()

    if target_user is None or not target_user.is_active:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if authenticated_user.id != user_id and authenticated_user.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt_profile)
    existing_profile = result.scalars().first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    filename = None
    if avatar:
        try:
            file_bytes = await avatar.read()
            filename = f"avatars/{user_id}_avatar.jpg"
            await s3_client.upload_file(filename, file_bytes)

        except S3FileUploadError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later.",
            )

        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later.",
            )

    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=first_name.lower() if first_name else None,
            last_name=last_name.lower() if last_name else None,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=filename,
        )

        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e

    return ProfileResponseSchema.model_validate(new_profile)
