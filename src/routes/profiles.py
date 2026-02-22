import pathlib
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Form,
    UploadFile,
    File
)
from pydantic import ValidationError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import UserProfileResponseSchema, UserProfileBaseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface

router = APIRouter()


async def get_current_user(
    token: str = Depends(get_token),
    auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    try:
        payload = auth_manager.decode_access_token(token=token)
    except BaseSecurityError as e:
        error_msg = str(e)
        if "expired" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not valid."
        )

    user_stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == user_id)
    )
    db_user = await db.scalar(user_stmt)
    if not db_user or not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    return db_user


@router.post(
    "/users/{user_id}/profile/",
    response_model=UserProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    if (
            user_id != current_user.id
            and current_user.group.name not in ("admin", "moderator")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    stmt_user = select(UserModel).where(UserModel.id == user_id)
    target_user = await db.scalar(stmt_user)
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    existing_profile = await db.scalar(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )
    try:
        profile_data = UserProfileBaseSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )
    except (ValueError, ValidationError) as e:
        error_msg = e.errors()[0]["msg"] if hasattr(e, "errors") else str(e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg
        )

    extension = pathlib.Path(avatar.filename).suffix
    file_name = f"avatars/{user_id}_avatar{extension}"
    avatar_content = await avatar.read()
    try:
        await s3_client.upload_file(
            file_name=file_name,
            file_data=avatar_content
        )
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=file_name,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    full_avatar_url = await s3_client.get_file_url(new_profile.avatar)
    response_data = UserProfileResponseSchema.model_validate(new_profile)
    response_data.avatar = full_avatar_url

    return response_data
