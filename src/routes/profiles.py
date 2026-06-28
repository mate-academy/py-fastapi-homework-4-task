from datetime import date, datetime, timezone
from typing import Annotated, Optional, cast
from fastapi import APIRouter, Depends, status, HTTPException, File, UploadFile, Form, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from database.models.accounts import UserModel, UserProfileModel
from config import get_jwt_auth_manager, get_s3_storage_client, get_settings
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from validation import validate_image

router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_db)]


def _validate_profile_fields(gender: Optional[str], info: Optional[str]) -> None:
    if gender not in ["man", "woman"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gender must be one of 'man' or 'woman'"
        )

    if info is not None and (info == "" or info.isspace()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Info field cannot be empty or contain only spaces."
        )


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    tags=["profiles"]
)
async def create_user_profile(
        user_id: int,
        db: SessionDep,
        authorization: Annotated[Optional[str], Header()] = None,
        avatar: Optional[UploadFile] = File(None),
        first_name: Optional[str] = Form(None),
        last_name: Optional[str] = Form(None),
        gender: Optional[str] = Form(None),
        date_of_birth: Optional[str] = Form(None),
        info: Optional[str] = Form(None),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header is missing")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    if any(p is None for p in [avatar, first_name, last_name, gender, date_of_birth, info]):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required fields")

    _validate_profile_fields(gender, info)

    token = authorization.split(" ")[1]
    try:
        decoded_data = jwt_manager.decode_access_token(token)
        current_user_id = decoded_data.get("user_id")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    if current_user_id != user_id:
        from sqlalchemy.orm import selectinload
        curr_user_stmt = select(UserModel).filter(UserModel.id == current_user_id).options(
            selectinload(UserModel.group))
        curr_user_res = await db.execute(curr_user_stmt)
        curr_user_obj = curr_user_res.scalar()

        if not curr_user_obj or getattr(curr_user_obj.group, "name", "") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You don't have permission to edit this profile.")

    try:
        parsed_date = date.fromisoformat(date_of_birth)
        profile_data = ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=parsed_date,
            info=info
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    target_user_stmt = select(UserModel).filter(UserModel.id == user_id)
    target_user_res = await db.execute(target_user_stmt)
    target_user_obj = target_user_res.scalar()

    if not target_user_obj or not target_user_obj.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    existing_profile_stmt = select(UserProfileModel).filter(UserProfileModel.user_id == user_id)
    existing_profile_res = await db.execute(existing_profile_stmt)
    if existing_profile_res.scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    avatar_contents = await avatar.read()
    ext = avatar.filename.split(".")[-1] if avatar.filename and "." in avatar.filename else "jpg"
    s3_filename = f"avatars/{user_id}_avatar.{ext}"

    from exceptions import S3ConnectionError, S3FileUploadError

    try:
        await s3_client.upload_file(
            file_name=s3_filename,
            file_data=avatar_contents
        )
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=s3_filename
    )

    try:
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)

        app_settings = get_settings()
        new_profile.avatar = f"{app_settings.S3_STORAGE_ENDPOINT}/{app_settings.S3_BUCKET_NAME}/{s3_filename}"

        return new_profile

    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating profile."
        )
