from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, UserProfileModel, UserGroupEnum, get_db
from exceptions.security import BaseSecurityError
from exceptions.storage import BaseS3Error
from schemas import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create user profile",
    description="Create a profile for a user (only for self, unless admin).",
)
async def create_profile(
    user_id: int,
    request: Request,
    data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    token = get_token(request)

    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    token_user_id = payload.get("user_id")
    if not token_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == int(token_user_id))
    )
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    is_admin = current_user.group and current_user.group.name == UserGroupEnum.ADMIN

    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    if current_user.id == user_id:
        target_user = current_user
    else:
        stmt_target = select(UserModel).where(UserModel.id == user_id)
        result_target = await db.execute(stmt_target)
        target_user = result_target.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result_profile = await db.execute(stmt_profile)
    existing_profile = result_profile.scalars().first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_bytes = await data.avatar.read()

    try:
        await s3_client.upload_file(avatar_key, avatar_bytes)
        avatar_url = await s3_client.get_file_url(avatar_key)
    except BaseS3Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        ) from exc

    profile = UserProfileModel(
        user_id=user_id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=data.gender_enum(),
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=avatar_key,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender.value,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
