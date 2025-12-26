from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupModel
from exceptions import S3ConnectionError, S3FileUploadError

from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from security.token_manager import JWTAuthManager

import exceptions as exp
from storages import S3StorageInterface

router = APIRouter()


async def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
    jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    try:
        payload = jwt_manager.decode_access_token(authorization.split(" ")[1])

    except exp.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    except exp.TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )

    token_user_id = payload.get("user_id")

    db_user = await db.scalar(select(UserModel).where(UserModel.id == token_user_id))

    return db_user


# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/accounts/login/")


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    db_user: UserModel = Depends(get_current_user),
    profile: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
):

    if not db_user or db_user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    db_user_group = await db.scalar(
        select(UserGroupModel).where(UserGroupModel.name == "ADMIN")
    )

    if db_user.id != user_id and db_user.group_id != db_user_group.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    db_profile = await db.scalar(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )

    if db_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
        file_name = f"avatars/{user_id}_avatar.jpg"
        file_data = await profile.avatar.read()

        await s3_client.upload_file(file_name=file_name, file_data=file_data)

        file_url = await s3_client.get_file_url(file_name=file_name)

        db_profile = UserProfileModel(
            first_name=profile.first_name.lower(),
            last_name=profile.last_name.lower(),
            gender=profile.gender,
            date_of_birth=profile.date_of_birth,
            info=profile.info,
            user_id=user_id,
            avatar=file_name,
        )

        db.add(db_profile)
        await db.commit()
        await db.refresh(db_profile)
        db_profile.avatar = file_url

        return db_profile

    except (S3ConnectionError, S3FileUploadError):
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating profile.",
        )
