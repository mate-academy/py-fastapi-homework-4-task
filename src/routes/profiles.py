from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import (
    get_db,
    UserModel,
    UserGroupEnum,
    UserProfileModel
)
from database.models.accounts import GenderEnum
from exceptions import (
    BaseSecurityError,
    S3ConnectionError,
    S3FileUploadError
)
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    description=(
            "Create a profile for the user. A user can create only their own "
            "profile, an admin can create a profile for any user."
    ),
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "Bad Request - User already has a profile.",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a profile."}
                }
            },
        },
        401: {
            "description": (
                "Unauthorized - Token is missing, invalid or expired, "
                "or the user is not found or not active."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "User not found or not active."}
                }
            },
        },
        403: {
            "description": "Forbidden - No permission to edit this profile.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission "
                                  "to edit this profile."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - Avatar upload failed.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to upload avatar. "
                                  "Please try again later."
                    }
                }
            },
        },
    },
)
async def create_profile(
        user_id: int,
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        profile_data: ProfileCreateSchema = Depends(
            ProfileCreateSchema.from_form
        ),
) -> ProfileResponseSchema:
    """
    Endpoint for creating a user profile.

    Steps:
        1. Decode the access token (401 if it is invalid or expired).
        2. Check that the requester is active and is either the profile
           owner or an admin (401 / 403).
        3. Check that the target user exists and is active (401).
        4. Check that the user has no profile yet (400).
        5. Upload the avatar to S3 storage (500 on failure).
        6. Save the profile to the database and return it (201).

    Args:
        user_id (int): The ID of the user the profile is created for.
        token (str): The Bearer token from the Authorization header.
        db (AsyncSession): The asynchronous database session.
        jwt_manager (JWTAuthManagerInterface): The JWT manager.
        s3_client (S3StorageInterface): The S3 storage client.
        profile_data (ProfileCreateSchema): The validated form data.

    Returns:
        ProfileResponseSchema: The created profile with the avatar URL.

    Raises:
        HTTPException: 400, 401, 403 or 500 as described above.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error)
        )

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == payload.get("user_id"))
    )
    query_result = await db.execute(stmt)
    requester = query_result.scalars().first()
    if not requester or not requester.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    is_admin = requester.group.name == UserGroupEnum.ADMIN
    if requester.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    stmt = select(UserModel).where(UserModel.id == user_id)
    query_result = await db.execute(stmt)
    user = query_result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    query_result = await db.execute(stmt)
    if query_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_bytes = await profile_data.avatar.read()
    try:
        await s3_client.upload_file(avatar_key, avatar_bytes)
    except (S3FileUploadError, S3ConnectionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=GenderEnum(profile_data.gender),
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
            detail="An error occurred while creating the profile."
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
