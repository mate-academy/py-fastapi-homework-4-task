from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from database.models.accounts import GenderEnum
from exceptions import BaseSecurityError, TokenExpiredError, S3FileUploadError
from schemas.profiles import ProfileCreateRequestSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
        user_id: int,
        token: str = Depends(get_token),
        data: ProfileCreateRequestSchema = Depends(ProfileCreateRequestSchema.as_form),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    try:
        token_user_id = jwt_manager.decode_access_token(token).get("user_id")
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if token_user_id != user_id:
        result = await db.execute(
            select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == token_user_id)
        )
        requester = result.scalars().first()
        if not requester or requester.group.name != UserGroupEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    avatar_key = f"avatars/{user_id}_{data.avatar.filename}"
    try:
        await s3_client.upload_file(avatar_key, await data.avatar.read())
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=GenderEnum(data.gender),
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=avatar_key,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=data.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=await s3_client.get_file_url(avatar_key),
    )
