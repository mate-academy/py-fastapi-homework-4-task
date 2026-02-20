from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel, UserGroupEnum, UserGroupModel
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import ProfileCreateResponseSchema, ProfileCreateSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileCreateResponseSchema,
    status_code=201
)
async def create_profile(
        user_id: int,
        data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    try:
        token_info = jwt_manager.decode_access_token(token)
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

    if token_info.get("user_id") != user_id:
        result = await db.execute(
            select(UserGroupModel).
            join(UserModel).
            where(UserModel.id == token_info.get("user_id"))
        )
        user_group = result.scalar_one_or_none()
        if not user_group or user_group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to edit this profile."
            )

    result = await db.execute(
        select(UserModel).options(selectinload(UserModel.profile)).where(UserModel.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    if user.profile:
        raise HTTPException(
            status_code=400,
            detail="User already has a profile."
        )

    avatar_bytes = data.avatar.read()
    avatar_name = f"avatars/{user_id}_{data.avatar.filename}"

    try:
        await s3_client.upload_file(avatar_name, avatar_bytes)
    except S3FileUploadError:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=avatar_name
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    avatar_url = await s3_client.get_file_url(avatar_name)
    return ProfileCreateResponseSchema(
        id=new_profile.id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url
    )
