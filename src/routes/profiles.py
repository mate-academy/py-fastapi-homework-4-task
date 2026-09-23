from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserGroupEnum, UserModel, UserProfileModel
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()

ELEVATED_GROUPS = frozenset({UserGroupEnum.ADMIN})


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def profile_creation(
        user_id: int,
        profile_data: Annotated[ProfileCreateSchema, Form()],
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    try:
        token_data = jwt_manager.decode_access_token(token)

    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )
    requester_id = token_data.get("user_id")
    requester = await db.scalar(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == requester_id)
    )

    is_owner = requester_id == user_id
    is_elevated = requester is not None and requester.group.name in ELEVATED_GROUPS

    if not (is_owner or is_elevated):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )
    profile_owner = await db.scalar(
        select(UserModel)
        .where(UserModel.id == user_id)
    )

    if not profile_owner or not profile_owner.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    existing_profile = await db.scalar(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if existing_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    file_data = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=file_data)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    url_stored_file = await s3_client.get_file_url(file_name=avatar_key)
    db_user = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )
    db.add(db_user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    return ProfileResponseSchema.model_validate(db_user).model_copy(
        update={"avatar": url_stored_file}
    )
