from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import BaseSecurityError, BaseS3Error
from schemas import ProfileCreateResponseSchema, ProfileCreateRequestSchema
from database import get_db, UserModel, UserGroupEnum, UserProfileModel

from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileCreateResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    request_data: ProfileCreateRequestSchema = Depends(
        ProfileCreateRequestSchema.from_form
    ),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileCreateResponseSchema:

    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error)
        )

    if user_id != token_user_id:
        stmt = (select(UserModel)
                .options(joinedload(UserModel.group))
                .filter_by(id=token_user_id))
        result = await db.execute(stmt)
        requester_user = result.scalars().first()
        if not requester_user or not requester_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )
        if not requester_user.has_group(UserGroupEnum.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    stmt = (select(UserModel)
            .options(joinedload(UserModel.profile))
            .filter_by(id=user_id))
    result = await db.execute(stmt)
    target_user = result.scalars().first()
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if target_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    avatar_key = f"avatars/{target_user.id}_avatar.jpg"
    try:
        avatar_bytes = await request_data.avatar.read()
        await s3_client.upload_file(avatar_key, avatar_bytes)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )
    avatar_url = await s3_client.get_file_url(avatar_key)

    profile = UserProfileModel(
        first_name=request_data.first_name,
        last_name=request_data.last_name,
        avatar=avatar_key,
        gender=request_data.gender,
        date_of_birth=request_data.date_of_birth,
        info=request_data.info,
        user_id=target_user.id
    )
    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while writing the profile.",
        )

    return ProfileCreateResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
