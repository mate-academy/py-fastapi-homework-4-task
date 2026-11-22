from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from exceptions import TokenExpiredError, InvalidTokenError, BaseS3Error
import os

router = APIRouter()

@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Profile",
    description="Create a profile for a user and upload an avatar."
)
async def create_user_profile(
    user_id: int,
    request: Request,
    profile_data: ProfileCreateSchema = Depends(),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileResponseSchema:
    token = get_token(request)
    
    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token."
        )
        
    token_user_id = payload.get("user_id")
    
    stmt = select(UserModel).options(joinedload(UserModel.group)).filter_by(id=token_user_id)
    result = await db.execute(stmt)
    token_user = result.scalars().first()
    
    if not token_user or not token_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if token_user_id != user_id and token_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    stmt = select(UserModel).options(joinedload(UserModel.profile)).filter_by(id=user_id)
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

    avatar_file = profile_data.avatar
    # Reset file pointer after validation read it
    await avatar_file.seek(0)
    file_bytes = await avatar_file.read()
    
    ext = os.path.splitext(avatar_file.filename)[1] if avatar_file.filename else ".jpg"
    avatar_filename = f"{user_id}_avatar{ext}"
    
    try:
        await s3_client.upload_file(avatar_filename, file_bytes)
        avatar_url = await s3_client.get_file_url(avatar_filename)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return ProfileResponseSchema.model_validate(new_profile)
