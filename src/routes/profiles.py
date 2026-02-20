from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database.models.accounts import GenderEnum
from exceptions import TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from fastapi import status

from security.http import get_token
from security.interfaces import JWTAuthManagerInterface

from database import get_db, UserModel, UserGroupModel, UserGroupEnum, UserProfileModel
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "Bad Request - Profile already exists or invalid data.",
            "content": {
                "application/json": {
                    "examples": {
                        "ProfileAlreadyExists": {
                            "summary": "Profile Already Exists",
                            "value": {"detail": "User already has a profile."}
                        }
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - Token missing, invalid, or expired.",
            "content": {
                "application/json": {
                    "examples": {
                        "MissingToken": {
                            "summary": "Missing Token",
                            "value": {"detail": "Authorization header is missing"}
                        },
                        "InvalidTokenFormat": {
                            "summary": "Invalid Token Format",
                            "value": {"detail": "Invalid Authorization header format. Expected 'Bearer <token>'"}
                        },
                        "ExpiredToken": {
                            "summary": "Expired Token",
                            "value": {"detail": "Token has expired."}
                        },
                        "UserNotFoundOrNotActive": {
                            "summary": "User Not Found or Not Active",
                            "value": {"detail": "User not found or not active."}
                        },
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - User does not have permission to modify this profile.",
            "content": {
                "application/json": {
                    "example": {"detail": "You don't have permission to edit this profile."}
                }
            }
        },
        500: {
            "description": "Internal Server Error - An error occurred while processing the request.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to upload avatar. Please try again later."
                    }
                }
            },
        },
    },
)
async def create_profile(
        user_id: int,
        data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    token_user_id = decoded_token.get("user_id")
    if not token_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    stmt_target_user = select(UserModel).where(UserModel.id == user_id)
    target_user = await db.scalar(stmt_target_user)

    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    stmt_current_user = select(UserModel).where(UserModel.id == token_user_id)
    current_user = await db.scalar(stmt_current_user)

    stmt_group = select(UserGroupModel.name).where(UserGroupModel.id == current_user.group_id)
    current_user_group = await db.scalar(stmt_group)

    is_admin = current_user_group == UserGroupEnum.ADMIN.value
    if user_id != token_user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    current_profile = await db.scalar(stmt_profile)

    if current_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    avatar = f"avatars/{user_id}_{data.avatar.filename}"
    try:
        avatar_bytes = await data.avatar.read()
        await s3_client.upload_file(file_name=avatar, file_data=avatar_bytes)
        avatar_url = await s3_client.get_file_url(avatar)
    except Exception:
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
        avatar=avatar
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )
