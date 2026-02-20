from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import JSONResponse

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileSchema, ProfileResponseSchema, get_form_data

from database import (
    get_db, UserModel, UserProfileModel, UserGroupEnum,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    description="User profile management: token validation, "
                "authorization, database storage and avatar upload logic",
)
async def profile_creation_endpoint(
        user_id: int,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        form_data: ProfileSchema = Depends(get_form_data),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        db: AsyncSession = Depends(get_db)
) -> JSONResponse:

    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    data_user, avatar = form_data

    existing_user = await db.execute(
        select(UserModel)
        .options(
            selectinload(UserModel.group),
            selectinload(UserModel.profile)
        )
        .filter(UserModel.id == user_id)
    )
    user_db = existing_user.scalar()
    if not user_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    requesting_user_id = int(decoded_token.get("user_id", -1))

    requesting_user_result = await db.execute(
        select(UserModel).
        options(selectinload(UserModel.group)).
        filter(UserModel.id == requesting_user_id)
    )
    requesting_user = requesting_user_result.scalar()

    if (
            requesting_user_id != user_id
            and (not requesting_user or
                 requesting_user.group.name != UserGroupEnum.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    if not user_db.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )
    if user_db.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    filename = f"avatars/{user_id}_avatar.jpg"
    contents = await avatar.read()
    try:
        await s3_client.upload_file(filename, contents)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    user_profile = UserProfileModel(
        first_name=data_user.first_name,
        last_name=data_user.last_name,
        avatar=filename,
        gender=data_user.gender,
        date_of_birth=data_user.date_of_birth,
        info=data_user.info,
        user_id=user_id,
    )
    db.add(user_profile)
    await db.commit()
    await db.refresh(user_profile)

    try:
        url_avatar = await s3_client.get_file_url(filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    response_data = ProfileResponseSchema(
        id=user_profile.id,
        user_id=user_profile.user_id,
        first_name=user_profile.first_name,
        last_name=user_profile.last_name,
        gender=user_profile.gender,
        date_of_birth=user_profile.date_of_birth,
        info=user_profile.info,
        avatar=url_avatar
    )
    return JSONResponse(
        content=jsonable_encoder(response_data),
        status_code=status.HTTP_201_CREATED
    )
