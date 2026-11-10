from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.concurrency import run_in_threadpool

from config.dependencies import (
    get_jwt_auth_manager,
    get_s3_storage_client,
)
from database import (
    UserGroupEnum,
    UserModel,
    UserProfileModel,
    get_db,
)
from exceptions import BaseSecurityError
from exceptions.storage import BaseS3Error
from schemas.profiles import (
    ProfileCreateSchema,
    ProfileResponseSchema,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


def convert_avatar_to_jpeg(contents: bytes) -> bytes:
    with Image.open(BytesIO(contents)) as image:
        converted_image = image.convert("RGB")

        try:
            with BytesIO() as output:
                converted_image.save(
                    output,
                    format="JPEG",
                    quality=90,
                )
                return output.getvalue()
        finally:
            converted_image.close()


async def get_current_profile_user(
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(
        get_jwt_auth_manager
    ),
) -> UserModel:
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    current_user_id = payload.get("user_id")

    if (
        not isinstance(current_user_id, int)
        or isinstance(current_user_id, bool)
        or current_user_id <= 0
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )
    user = result.scalars().first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    return user


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create user profile",
)
async def create_user_profile(
    user_id: int,
    current_user: UserModel = Depends(get_current_profile_user),
    profile_data: ProfileCreateSchema = Depends(
        ProfileCreateSchema.as_form
    ),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(
        get_s3_storage_client
    ),
) -> ProfileResponseSchema:
    is_admin = current_user.has_group(UserGroupEnum.ADMIN)

    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    result = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    target_user = result.scalars().first()

    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    result = await db.execute(
        select(UserProfileModel).where(
            UserProfileModel.user_id == user_id
        )
    )
    existing_profile = result.scalars().first()

    if existing_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{user_id}_avatar.jpg"

    await profile_data.avatar.seek(0)
    original_contents = await profile_data.avatar.read()

    avatar_contents = await run_in_threadpool(
        convert_avatar_to_jpeg,
        original_contents,
    )

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

        # Check database constraints before uploading the avatar.
        await db.flush()

        try:
            await s3_client.upload_file(
                avatar_key,
                avatar_contents,
            )
            avatar_url = await s3_client.get_file_url(avatar_key)
        except BaseS3Error as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Failed to upload avatar. "
                    "Please try again later."
                ),
            ) from error

        response = ProfileResponseSchema(
            id=profile.id,
            user_id=profile.user_id,
            first_name=profile.first_name,
            last_name=profile.last_name,
            gender=profile.gender,
            date_of_birth=profile.date_of_birth,
            info=profile.info,
            avatar=avatar_url,
        )

        await db.commit()

    except HTTPException:
        await db.rollback()
        raise

    except IntegrityError as error:
        await db.rollback()

        result = await db.execute(
            select(UserProfileModel.id).where(
                UserProfileModel.user_id == user_id
            )
        )

        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a profile.",
            ) from error

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation.",
        ) from error

    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation.",
        ) from error

    return response
