import uuid
from io import BytesIO

from PIL import Image
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import get_s3_storage_client
from database import UserProfileModel, UserModel, get_db
from routes.accounts import get_current_user
from schemas.profiles import ProfileSchema, ProfileResponseSchema
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    user_data: ProfileSchema = Depends(ProfileSchema.as_form),
    user: UserModel = Depends(get_current_user),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
):
    user_with_id = await db.get(UserModel, user_id)

    if not user_with_id or not user_with_id.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if user is not user_with_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    profile = await db.scalar(stmt)

    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    profile = UserProfileModel(user_id=user_id, **user_data.model_dump(exclude={"avatar"}))

    try:
        if user_data.avatar:
            avatar_bytes = await user_data.avatar.read()
            img = Image.open(BytesIO(avatar_bytes))
            ext = img.format.lower()

            if ext == "jpeg":
                ext = "jpg"

            unique_suffix = uuid.uuid4().hex[:8]
            file_name = f"profiles/{user_id}_{unique_suffix}.{ext}"

            profile.avatar = await s3_client.upload_file(
                file_name=file_name,
                file_data=avatar_bytes
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return profile
