from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import HttpUrl
from sqlalchemy import select, cast
from sqlalchemy.ext.asyncio import AsyncSession


from database import get_db, UserGroupModel, UserModel, UserProfileModel
from config import get_s3_storage_client, get_jwt_auth_manager
from database.models.accounts import TokenBaseModel, UserGroupEnum, GenderEnum
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED,)
async def create_profile(
        user_id: int,
        profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_request),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    existing_profile = result.scalars().first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        token_payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    token_user_id = token_payload.get("user_id")

    if user_id != token_user_id:
        stmt = (
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == token_user_id)
        )
        result = await db.execute(stmt)
        user_group = result.scalars().first()
        if not user_group or user_group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    file_data = await profile_data.avatar.read()
    avatar_url = f"avatars/{user_id}_{profile_data.avatar.filename}"

    try:
        await s3_client.upload_file(avatar_url, file_data)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    user_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url
    )
    db.add(user_profile)
    await db.commit()
    await db.refresh(user_profile)

    return ProfileResponseSchema(
        id=user_profile.id,
        user_id=user_id,
        first_name=user_profile.first_name,
        last_name=user_profile.last_name,
        gender=user_profile.gender,
        date_of_birth=user_profile.date_of_birth,
        info=user_profile.info,
        avatar=avatar_url
    )
