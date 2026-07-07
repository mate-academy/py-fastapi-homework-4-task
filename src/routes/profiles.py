from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from database import get_db
from database.models.accounts import UserGroupEnum, UserModel, UserProfileModel
from exceptions.security import InvalidTokenError, TokenExpiredError
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface

import schemas


router = APIRouter()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    bearer_token = get_token(request)

    try:
        jwt_manager.verify_access_token_or_raise(bearer_token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    token_data = jwt_manager.decode_access_token(bearer_token)
    token_user_id = token_data["user_id"]

    result = await db.scalars(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == token_user_id)
    )
    user = result.first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    return user


@router.post(
    "/users/{user_id}/profile/",
    response_model=schemas.ProfileDetailSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
    user_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    profile_data: schemas.ProfileCreateSchema = Depends(schemas.ProfileCreateSchema.as_form),
):
    if not (
        current_user.id == user_id or current_user.group.name == UserGroupEnum.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    result = await db.scalars(select(UserModel).where(UserModel.id == user_id))
    user = result.first()

    if not (user and user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    profile_result = await db.scalars(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    existing_profile = profile_result.first()

    if existing_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    filename = f"avatars/{user.id}_avatar.jpg"
    fcontents = await profile_data.avatar.read()

    try:
        await s3_client.upload_file(file_name=filename, file_data=fcontents)
        avatar_url = await s3_client.get_file_url(file_name=filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        ) from e

    profile = UserProfileModel(
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=filename,
        user=user
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return schemas.ProfileDetailSchema.model_validate(profile).model_copy(
        update={"avatar": avatar_url}
    )
