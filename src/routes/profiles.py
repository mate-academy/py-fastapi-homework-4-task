from idlelib.rpc import response_queue

from aiohttp.web_fileresponse import extension
from fastapi import APIRouter, UploadFile, File, Depends, status, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.future import select
from config import get_s3_storage_client, get_jwt_auth_manager
from schemas.profiles import ProfileCreateFormSchema, ProfileResponseSchema
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token, get_current_user
from storages import S3StorageInterface
import os
from validation import validate_image

router = APIRouter()


# Write your code here
@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create a user profile",
    description="Create a user profile eith avatar upload to S3 storage.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "Bad Request - User already has a profile",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a profile."}
                }
            },
        },
        401: {
            "description": "Unauthorized - Missing, invalid, or expired token; user not found or not active",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_token": {
                            "summary": "Missing Authorization Header",
                            "value": {"detail": "Authorization header is missing"}
                        },
                        "invalid_format": {
                            "summary": "Invalid Authorization Format",
                            "value": {"detail": "Invalid Authorization header format. Expected 'Bearer <token>'"}
                        },
                        "expired_token": {
                            "summary": "Expired Token",
                            "value": {"detail": "Token has expired."}
                        },
                        "user_not_found": {
                            "summary": "User Not Found or Not Active",
                            "value": {"detail": "User not found or not active."}
                        }
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - User doesn't have permission to edit this profile",
            "content": {
                "application/json": {
                    "example": {"detail": "You don't have permission to edit this profile."}
                }
            },
        },
        500: {
            "description": "Internal Server Error - Avatar upload failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to upload avatar. Please try again later."}
                }
            },
        },
    }
)
async def create_profile(
        user_id: int,
        profile_data: ProfileCreateFormSchema = Depends(ProfileCreateFormSchema.as_form),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        current_user: UserModel = Depends(get_current_user),
) -> ProfileResponseSchema:
    """
    Create a user profile with an avatar upload to S3 storage.

    :param user_id: ID of the user for whom the profile is being created.
    :param user: ProfileCreateFormSchema containing profile data.
    :param db: Database session dependency.
    :param s3_client: S3 storage client dependency.
    :param current_user: Current authenticated user.
    :return: ProfileResponseSchema containing the created profile data.
    """

    if current_user.id != user_id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    existing_profile = result.scalars().first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    avatar_key = f"avatars/{user_id}_avatar.{profile_data.avatar.filename.split('.')[-1]}"
    try:
        avatar_content = await profile_data.avatar.read()
        await s3_client.upload_file(avatar_key, avatar_content)
        avatar_url = await s3_client.get_file_url(avatar_key)
    except Exception:
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
        avatar=avatar_key
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    response_data = ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name or "",
        last_name=new_profile.last_name or "",
        gender=new_profile.gender.value if new_profile.gender else "",
        date_of_birth=new_profile.date_of_birth or profile_data.date_of_birth,
        info=new_profile.info or "",
        avatar=avatar_url
    )

    return response_data
