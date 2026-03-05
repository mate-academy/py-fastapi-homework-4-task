from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config.dependencies import get_s3_storage_client
from database import get_db
from config import get_jwt_auth_manager
from database.models.accounts import UserGroupEnum, UserModel, UserProfileModel
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from schemas import (
    ProfileResponseSchema,
    ProfileRequestSchema
)
from exceptions import (
    BaseSecurityError,
    TokenExpiredError,
    InvalidTokenError
)
from storages.interfaces import S3StorageInterface

router = APIRouter()


async def auth_user(
    request: Request,
    jwt_auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    token = get_token(request)

    try:
        body = jwt_auth_manager.decode_access_token(token)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    user_id = body.get("user_id")
    user = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == user_id)
    )
    user = user.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")
    return user


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    request: Request,
    jwt_auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db)
) -> ProfileResponseSchema:
    user = await auth_user(request, jwt_auth_manager, db)

    if user.id != user_id and not user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    user_by_param = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user_by_param = user_by_param.scalar_one_or_none()

    if not user_by_param or not user_by_param.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    form = await request.form()
    info_raw = form.get("info")

    if info_raw is None or not str(info_raw).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Info field cannot be empty or contain only spaces.",
        )
    avatar = form.get("avatar")
    try:
        profile_data = ProfileRequestSchema(
            first_name=form.get("first_name"),
            last_name=form.get("last_name"),
            gender=form.get("gender"),
            date_of_birth=form.get("date_of_birth"),
            info=form.get("info"),
            avatar=avatar,
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=jsonable_encoder(e.errors()))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    profile = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    profile = profile.scalar_one_or_none()
    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info
    )
    file_extension = profile_data.avatar.filename.split(".")[-1]
    avatar_key = f"avatars/{user_id}_avatar.{file_extension}"
    file_data = await profile_data.avatar.read()
    try:
        await s3_client.upload_file(
            file_name=avatar_key,
            file_data=file_data,
            content_type=profile_data.avatar.content_type
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
    profile.avatar = avatar_key
    avatar_url = await s3_client.get_file_url(avatar_key)

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )
