from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pyasn1.codec.ber.decoder import stDecodeTag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from security import get_token, decode_access_token

from database import get_db
from schemas import ProfileResponseSchema


from config.dependencies import get_s3_storage_client
from database.models.accounts import UserModel, UserGroupModel, UserProfileModel
from storages.interfaces import S3StorageInterface

router = APIRouter()

# Write your code here
@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=201)
async def profile_create(user_id: int, user_data: ProfileResponseSchema, avatar: UploadFile = File(...), s3_client: S3StorageInterface = Depends(get_s3_storage_client), db: AsyncSession = Depends(get_db), token: str = Depends(get_token)):
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    decode_access = decode_access_token(token)
    if not decode_access:
        raise HTTPException(status_code=404, detail="Invalid Token")

    if decode_access["exp"] > datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token has expired.")

    result_user = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = await result_user.scalar_one_or_none()
    result_group = await db.execute(select(UserGroupModel).filter(UserGroupModel.name == "ADMIN"))
    group = await result_group.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if user_id != decode_access["user_id"]:
        if user.group_id != group.id:
            raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    result_user_profile = await db.execute(select(UserProfileModel).filter(UserProfileModel.user_id == user.id))
    user_profile = await result_user_profile.scalar_one_or_none()

    if user_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    filename = f"http://minio-theater/avatars/{user.id}_avatar.jpg"
    try:
        file_data = await avatar.read()
        await s3_client.upload_file(file_name=filename, file_data=file_data)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile_user = UserProfileModel(
        user_id=user.id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        gender=user_data.gender,
        date_of_birth=user_data.date_of_birth,
        info=user_data.info,
        avatar=filename
    )

    db.add(profile_user)
    await db.commit()
    await db.refresh(profile_user)

    return {
        "id": profile_user.id,
        "user_id": profile_user.user_id,
        "first_name": profile_user.first_name,
        "last_name": profile_user.last_name,
        "gender": profile_user.gender,
        "date_of_birth": profile_user.date_of_birth,
        "info": profile_user.info,
        "avatar": profile_user.avatar
    }