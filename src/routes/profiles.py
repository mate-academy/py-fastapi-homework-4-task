from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create user profile",
    description="Create a profile for a user. Users can create only their own profile, admins - any.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "User already has a profile."},
        401: {
            "description": "Missing/invalid/expired token, or user not found or not active."
        },
        403: {"description": "You don't have permission to edit this profile."},
        422: {"description": "Validation error."},
        500: {"description": "Failed to upload avatar. Please try again later."},
    },
)
async def create_profile(
    user_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
) -> ProfileResponseSchema:
    """
    Create a profile for the given user.

    Steps: validate token -> check permissions -> check target user ->
    check that profile doesn't exist -> upload avatar -> save profile.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))

    token_user_id = payload.get("user_id")

    if token_user_id != user_id:
        stmt = (
            select(UserModel)
            .options(joinedload(UserModel.group))
            .where(UserModel.id == token_user_id)
        )
        result = await db.execute(stmt)
        requester = result.scalars().first()
        if not requester or requester.group.name != UserGroupEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    try:
        avatar_bytes = await profile_data.avatar.read()
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
    except (BaseS3Error, OSError):
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
        avatar=avatar_key,
    )
    try:
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the profile.",
        )

    avatar_url = await s3_client.get_file_url(avatar_key)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url,
    )
