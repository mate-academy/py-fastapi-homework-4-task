from datetime import date
from io import BytesIO

from PIL import Image
from fastapi import APIRouter, Depends, Request, HTTPException, status, Form, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_s3_storage_client
from database import get_db, UserModel, UserProfileModel
from database.models.accounts import GenderEnum
from exceptions import S3FileUploadError, S3ConnectionError
from schemas.profiles import ProfileResponseSchema, ProfileSchema
from security.utils import require_authorization
from storages import S3StorageInterface

router = APIRouter()


# Write your code here
@router.post(
    path="/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProfileResponseSchema
)
async def create_profile(
        user_id: int,
        request: Request,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        retrieved_user_id: int = Depends(require_authorization)
) -> ProfileResponseSchema:
    profile = ProfileSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar
    )

    user_db = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group), selectinload(UserModel.profile))
        .where(UserModel.id == retrieved_user_id)
    )
    user_db = user_db.scalar_one_or_none()
    if not user_db or not user_db.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if user_id != retrieved_user_id and user_db.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )
    target_user = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    target_user = target_user.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found or not active."
        )

    user_db = target_user if user_id != retrieved_user_id else user_db
    if user_db.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )
    file_bytes = await profile.avatar.read()
    image_filename = f"avatars/{user_db.id}_{profile.avatar.filename}"
    try:
        await s3_client.upload_file(image_filename, file_bytes)
        url = await s3_client.get_file_url(image_filename)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
    gender = GenderEnum.MAN if profile.gender == "man" else GenderEnum.WOMAN

    db_profile = UserProfileModel(
        first_name=profile.first_name.lower(),
        last_name=profile.last_name.lower(),
        avatar=image_filename,
        gender=gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        user_id=user_db.id,
        user=user_db
    )
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return ProfileResponseSchema.model_validate(
        {**db_profile.__dict__, "avatar": url}
    )
