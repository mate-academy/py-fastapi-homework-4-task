from fastapi import (
    APIRouter,
    HTTPException,
    status
)
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from database.models.accounts import GenderEnum
from exceptions import TokenExpiredError
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema

from database import (
    get_db,
    UserGroupEnum,
    UserModel,
    UserProfileModel,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create user profile",
    description="Create a profile for the authenticated user.",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {
            "description": (
                "Unauthorized - missing token, invalid token format, "
                "expired token, user not found or not active."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "missing_token": {
                            "summary": "Missing token",
                            "value": {
                                "detail": "Authorization header is missing"
                            }
                        },
                        "invalid_token_format": {
                            "summary": "Invalid token format",
                            "value": {
                                "detail": (
                                    "Invalid Authorization header format. Expected 'Bearer <token>'"
                                )
                            }
                        },
                        "expired_token": {
                            "summary": "Expired token",
                            "value": {
                                "detail": "Token has expired."
                            }
                        },
                        "inactive_user": {
                            "summary": "Inactive or missing user",
                            "value": {
                                "detail": "User not found or not active."
                            }
                        }
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - User cannot create another user profile.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to edit this profile."
                    }
                }
            },
        },
        400: {
            "description": "Bad request - User already has a profile.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User already has a profile."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - There was an error loading an avatar.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to upload avatar. Please try again later."
                    }
                }
            },
        },
    }
)
async def create_profile(
        user_id: int,
        profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
        token: str = Depends(get_token),
        jwt_auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    """
    Create user profile.
    """
    try:
        jwt_auth_manager.verify_access_token_or_raise(token)
        payload = jwt_auth_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    current_user_id = payload["user_id"]

    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )

    current_user = result.scalar_one_or_none()

    if current_user_id != user_id and current_user.group.name != UserGroupEnum.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    result = await db.execute(
        select(UserModel).where(
            UserModel.id == user_id,
            UserModel.is_active.is_(True),
        )
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    profile_result = await db.execute(
        select(UserProfileModel).where(
            UserProfileModel.user_id == user_id,
        )
    )
    existing_profile = profile_result.scalar_one_or_none()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    profile_data.avatar.file.seek(0)

    avatar_bytes = await profile_data.avatar.read()

    file_extension = profile_data.avatar.filename.split(".")[-1].lower()

    file_name = f"avatars/{user_id}_avatar.{file_extension}"

    try:
        await s3_client.upload_file(
            file_name=file_name,
            file_data=avatar_bytes
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=GenderEnum(profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=file_name,
    )

    db.add(profile)

    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3_client.get_file_url(profile.avatar)

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
