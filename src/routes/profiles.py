from datetime import date

from fastapi.params import Form, File
from fastapi import APIRouter, Depends, UploadFile, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, MovieModel, ProfileModel

from schemas.profiles import ProfileResponseSchema

from database.models.accounts import UserModel

from routes.dependency import get_current_user

from config.dependencies import get_s3_storage_client

from storages.interfaces import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema)
async def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
):

    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")
    result = await db.execute(select(ProfileModel).where(ProfileModel.user_id == user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already has a profile.")

    try:
        avatar_url = await s3_client.upload_avatar(user_id=user_id, avatar_file=avatar)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    new_profile = ProfileModel(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info.strip(),
        avatar=avatar_url
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return new_profile
