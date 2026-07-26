from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import (
    get_db,
    UserModel,
    UserGroupEnum,
    UserProfileModel
)
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    description="Create a profile for the given user and upload the avatar to S3 storage.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "Bad Request - The user already has a profile.",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a profile."}
                }
            },
        },
        401: {
            "description": "Unauthorized - The token is missing, malformed or expired, "
                           "or the user does not exist or is not active.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_header": {
                            "summary": "Missing Authorization header",
                            "value": {"detail": "Authorization header is missing"},
                        },
                        "invalid_header": {
                            "summary": "Invalid Authorization header format",
                            "value": {
                                "detail": "Invalid Authorization header format. Expected 'Bearer <token>'"
                            },
                        },
                        "expired_token": {
                            "summary": "Expired token",
                            "value": {"detail": "Token has expired."},
                        },
                        "inactive_user": {
                            "summary": "User not found or not active",
                            "value": {"detail": "User not found or not active."},
                        },
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - The user is not allowed to edit this profile.",
            "content": {
                "application/json": {
                    "example": {"detail": "You don't have permission to edit this profile."}
                }
            },
        },
        500: {
            "description": "Internal Server Error - The avatar could not be uploaded.",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to upload avatar. Please try again later."}
                }
            },
        },
    },
)
async def create_profile(
        user_id: int,
        token: str = Depends(get_token),
        profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    """
    Endpoint for creating a user profile.

    Validates the access token, checks that the requester is allowed to create the profile,
    uploads the avatar to the S3-compatible storage and stores the profile in the database.

    Args:
        user_id (int): The id of the user the profile is created for.
        token (str): The Bearer token extracted from the Authorization header.
        profile_data (ProfileCreateSchema): The validated profile form data.
        db (AsyncSession): The asynchronous database session.
        jwt_manager (JWTAuthManagerInterface): The JWT authentication manager.
        s3_client (S3StorageInterface): The S3-compatible storage client.

    Returns:
        ProfileResponseSchema: The newly created profile with a public avatar URL.

    Raises:
        HTTPException:
            - 401 Unauthorized if the token is invalid/expired or the user is missing or inactive.
            - 403 Forbidden if the requester may not create a profile for this user.
            - 400 Bad Request if the user already has a profile.
            - 500 Internal Server Error if the avatar upload fails.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == token_user_id)
    )
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    is_admin = current_user.has_group(UserGroupEnum.ADMIN)
    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    if current_user.id == user_id:
        target_user = current_user
    else:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await db.execute(stmt)
        target_user = result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == target_user.id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{target_user.id}_avatar.jpg"
    await profile_data.avatar.seek(0)
    avatar_bytes = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=target_user.id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3_client.get_file_url(avatar_key)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
