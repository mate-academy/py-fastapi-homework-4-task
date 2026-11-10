from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import BaseSecurityError, BaseS3Error, S3ConnectionError, S3FileUploadError
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Form,
    File,
    UploadFile,
)
from pydantic import ValidationError
from fastapi.exceptions import RequestValidationError
from datetime import date

from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import (
    get_db,
    UserGroupModel,
    UserModel,
    UserGroupEnum,
    UserProfileModel,
)
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        token_payload = jwt_manager.decode_access_token(token)
        token_user_id = token_payload.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    if token_user_id != user_id:
        group = await db.scalar(
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == token_user_id)
        )

        if group is None or group.name != UserGroupEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    user = await db.get(UserModel, user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    existing_profile = await db.scalar(
        select(UserProfileModel).where(
            UserProfileModel.user_id == user_id
        )
    )

    if existing_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
        profile_data = ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors())

    avatar_content = await avatar.read()
    avatar_key = f"avatars/{user_id}_{avatar.filename}"

    try:
        await s3_client.upload_file(avatar_key, avatar_content)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile_fields = profile_data.model_dump(exclude={"avatar"})

    profile = UserProfileModel(
        user_id=user_id,
        avatar=avatar_key,
        **profile_fields,
    )

    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile.",
        )

    avatar_url = await s3_client.get_file_url(avatar_key)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=user_id,
        avatar=avatar_url,
        **profile_fields,
    )
