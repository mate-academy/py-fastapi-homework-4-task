from fastapi import APIRouter, HTTPException, Security, status
from fastapi.params import Depends
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database import (
    UserGroupEnum,
    UserGroupModel,
    UserModel,
    UserProfileModel,
    get_db,
)
from database.models.accounts import GenderEnum
from exceptions import (
    InvalidTokenError,
    S3ConnectionError,
    S3FileUploadError,
    TokenExpiredError,
)
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter(
    dependencies=[Security(HTTPBearer(auto_error=False))]
)


async def get_user_by_id(
    user_id: int,
    db: AsyncSession,
) -> UserModel | None:
    return await db.scalar(
        select(UserModel)
        .where(UserModel.id == user_id)
    )


async def get_admin_group_id(
    db: AsyncSession,
) -> int | None:
    return await db.scalar(
        select(UserGroupModel.id)
        .where(UserGroupModel.name == UserGroupEnum.ADMIN)
    )


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    profile_data: ProfileRequestSchema = Depends(
        ProfileRequestSchema.as_form
    ),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    token: str = Depends(get_token),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    try:
        token_data = jwt_manager.decode_access_token(token)
        token_user_id = token_data.get("user_id")

        if not token_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found."
            )

        current_user = await get_user_by_id(user_id=token_user_id, db=db)

        if not current_user or not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active.",
            )

        current_user_group_id = current_user.group_id
        admin_group_id = await get_admin_group_id(db)

        if token_user_id != user_id and current_user_group_id != admin_group_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

        user = await get_user_by_id(user_id=user_id, db=db)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )

        profile = await db.scalar(
            select(UserProfileModel)
            .where(UserProfileModel.user_id == user_id)
        )

        if profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a profile."
            )

        avatars_filepath = f"avatars/{user.id}_avatar.jpg"
        avatar_data = await profile_data.avatar.read()

        await s3_client.upload_file(
            file_name=avatars_filepath,
            file_data=avatar_data,
        )

        file_url = await s3_client.get_file_url(
            file_name=avatars_filepath,
        )

        data = profile_data.model_dump()
        data.update({
            "user_id": user_id,
            "avatar": avatars_filepath,
            "gender": GenderEnum(profile_data.gender),
        })

        profile = UserProfileModel(**data)

        db.add(profile)
        await db.commit()
        await db.refresh(profile)

        response_data = {
            **data,
            "id": profile.id,
            "avatar": file_url,
        }

        return ProfileResponseSchema.model_validate(response_data)

    except HTTPException:
        raise

    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    except SQLAlchemyError:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )

    except (S3ConnectionError, S3FileUploadError):
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )
