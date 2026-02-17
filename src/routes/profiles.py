from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, File, Form, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel
from database.models.accounts import UserGroupModel
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info
)

router = APIRouter()


@router.post("/users/{user_id}/profile/", status_code=201, response_model=ProfileResponseSchema)
async def create_user_profile(
        request: Request,
        user_id: int = Path(),
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        db: AsyncSession = Depends(get_db),
        token_header: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),

):

    try:
        profile_data = ProfileCreateSchema(
            first_name=validate_name(first_name),
            last_name=validate_name(last_name),
            gender=validate_gender(gender),
            date_of_birth=validate_birth_date(date_of_birth),
            info=validate_info(info),
            avatar=validate_image(avatar)
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header is missing")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'")

    try:
        decoded_token = jwt_manager.decode_access_token(token_header)
    # Error handling returns the specified messages and status codes for each scenario.
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
        )

    current_user_id = decoded_token.get("user_id")
    current_user_group_name = await db.scalar(
        select(UserGroupModel.name)
        .select_from(UserModel)
        .join(UserModel.group)
        .where(UserModel.id == current_user_id)
    )

    if user_id != current_user_id and current_user_group_name != "admin":
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .filter_by(id=user_id)
    )
    db_user = result.scalar_one_or_none()

    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if db_user.profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    contents = await profile_data.avatar.read()
    image_format_type = profile_data.avatar.content_type.split("/")[-1]
    image_format_type = "jpg" if image_format_type == "jpeg" else image_format_type
    file_name = f"avatars/{db_user.id}_avatar.{image_format_type}"

    try:
        await s3_client.upload_file(file_name=file_name, file_data=contents)
    except BaseS3Error:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    db_user.profile = UserProfileModel(
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=await s3_client.get_file_url(file_name)
    )
    await db.commit()
    await db.refresh(db_user, ["profile"])

    return ProfileResponseSchema.model_validate(db_user.profile)
