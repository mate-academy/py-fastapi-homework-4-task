from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import BaseSecurityError, S3FileUploadError
from schemas import ProfileRequestSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from config.dependencies import get_s3_storage_client
from storages.interfaces import S3StorageInterface


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    description="Create a profile for a user.",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {
            "description": "Unauthorized",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_token": {
                            "summary": "Missing Token",
                            "value": {
                                "detail": "Authorization header is missing"
                            },
                        },
                        "invalid_token_format": {
                            "summary": "Invalid Token Format",
                            "value": {
                                "detail": (
                                    "Invalid Authorization header format. "
                                    "Expected 'Bearer <token>'"
                                )
                            },
                        },
                        "expired_token": {
                            "summary": "Expired Token",
                            "value": {
                                "detail": "Token has expired."
                            },
                        },
                        "user_not_found_or_inactive": {
                            "summary": "User Not Found or Not Active",
                            "value": {
                                "detail": "User not found or not active."
                            },
                        },
                    }
                }
            },
        },
        403: {
            "description": "Forbidden",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "You don't have permission to edit this profile."
                        )
                    }
                }
            },
        },
        400: {
            "description": "Bad Request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User already has a profile."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Failed to upload avatar. "
                            "Please try again later."
                        )
                    }
                }
            },
        },
    },
)
async def create_profile(
    user_id: int,
    profile_data: ProfileRequestSchema = Depends(
        ProfileRequestSchema.as_form
    ),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:

    try:
        decoded_token = jwt_manager.decode_access_token(token)
        current_user_id = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .filter_by(id=current_user_id)
    )
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if (
        current_user.id != user_id
        and not current_user.has_group(UserGroupEnum.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    stmt = select(UserModel).filter_by(id=user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    stmt = select(UserProfileModel).filter_by(user_id=user_id)
    result = await db.execute(stmt)
    existing_profile = result.scalars().first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"
    avatar_data = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(
            avatar_key,
            avatar_data,
        )
    except S3FileUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        ) from error

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the profile.",
        ) from error

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
