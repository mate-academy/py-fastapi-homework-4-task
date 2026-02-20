import os.path

from fastapi import APIRouter, status, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_s3_storage_client
from database import UserModel, get_db, UserGroupEnum, UserProfileModel
from schemas import ProfileResponseSchema, ProfileRequestSchema
from security.user_manager import get_current_user
from storages import S3StorageClient

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    responses={},
)
async def create_profile(
        user_id: int,
        profile_fields: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageClient = Depends(get_s3_storage_client),
):
    if current_user.id != user_id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    if current_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
        file = await profile_fields.avatar.read()
        name, extension = os.path.splitext(profile_fields.avatar.filename)
        filename = f"avatars/{user_id}_avatar{extension}"
        await s3_client.upload_file(filename, file)
        avatar_url = await s3_client.get_file_url(filename)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_fields.first_name.lower(),
        last_name=profile_fields.last_name.lower(),
        gender=profile_fields.gender,
        date_of_birth=profile_fields.date_of_birth,
        info=profile_fields.info.strip(),
        avatar=filename
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )
