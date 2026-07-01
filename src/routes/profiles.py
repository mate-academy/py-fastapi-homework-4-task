from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Header,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from pydantic import ValidationError
from typing import Optional

from database import get_db
from database.models.accounts import UserModel, UserProfileModel
from schemas.profiles import ProfileCreateRequest, ProfileResponseSchema
from storages import S3StorageInterface
from config.dependencies import get_s3_storage_client, get_jwt_auth_manager

from validation.profile import validate_image

router = APIRouter(prefix="", tags=["Profiles"])


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    date_of_birth: Optional[date] = Form(None),
    info: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    auth_manager=Depends(get_jwt_auth_manager),
    authorization: Optional[str] = Header(None),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    try:
        payload = auth_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )

    token_user_stmt = select(UserModel).where(UserModel.id == current_user_id)
    token_user_result = await db.execute(token_user_stmt)
    current_user = token_user_result.scalar_one_or_none()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    is_admin = current_user.group_id == 3

    if current_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Field required"
        )

    try:
        ProfileCreateRequest(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
        )
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"].replace("Value error, ", "")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg
        )

    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )

    target_user_stmt = select(UserModel).where(UserModel.id == user_id)
    target_user_result = await db.execute(target_user_stmt)
    target_user = target_user_result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    profile_stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    profile_result = await db.execute(profile_stmt)
    existing_profile = profile_result.scalar_one_or_none()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
        object_name = f"avatars/{user_id}_avatar.jpg"
        avatar_bytes = await avatar.read()
        await s3_client.upload_file(file_name=object_name, file_data=avatar_bytes)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower() if first_name else "",
        last_name=last_name.lower() if last_name else "",
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=object_name,
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    avatar_url = await s3_client.get_file_url(object_name)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url,
    )
