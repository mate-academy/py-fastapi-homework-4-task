from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import CreateProfileRequestSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def get_current_user(
        request: Request,
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    token = get_token(request)

    try:
        decoded = jwt_manager.decode_access_token(token)
        user_id = decoded.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    return user


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Profile",
)
async def create_user_profile(
        user_id: int,
        profile_data: CreateProfileRequestSchema = Depends(),
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    is_admin = current_user.group is not None and current_user.group.name == UserGroupEnum.ADMIN
    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    existing_profile = result.scalars().first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_data = profile_data.avatar.file.read()

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_data)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    avatar_url = await s3_client.get_file_url(avatar_key)

    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            gender=profile_data.gender,
            date_of_birth=profile_data.date_of_birth,
            info=profile_data.info,
            avatar=avatar_key,
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the profile.",
        )

    return ProfileResponseSchema(
        id=new_profile.id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url,
    )
