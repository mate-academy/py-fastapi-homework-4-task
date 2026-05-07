from datetime import datetime

from fastapi import APIRouter, status, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_current_user, get_s3_storage_client
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from database import get_db, UserModel, UserGroupEnum, UserProfileModel, UserGroupModel
from storages import S3StorageInterface
from validation import validate_image, validate_name, validate_gender, validate_birth_date

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
        user_id: int,
        profile_data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
        avatar: UploadFile = File(),
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        validate_name(profile_data.first_name)
        validate_name(profile_data.last_name)
        validate_gender(profile_data.gender)

        try:
            birth_date = datetime.strptime(profile_data.date_of_birth, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("Invalid birth date format. Expected YYYY-MM-DD.") from exc

        validate_birth_date(birth_date)

        if not profile_data.info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")

        validate_image(avatar)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc)
        ) from exc

    admin_group_id = await db.scalar(select(UserGroupModel.id).where(UserGroupModel.name == UserGroupEnum.ADMIN))
    if current_user.id != user_id and current_user.group_id != admin_group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN ,
            detail="You don't have permission to edit this profile."
        )

    user_profile = await db.scalar(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if user_profile:
        raise HTTPException(
            status_code=400,
            detail="User already has a profile."
        )

    avatar_bytes = await avatar.read()

    if not avatar.filename:
        raise HTTPException(400, detail="Avatar filename is missing.")

    try:
        avatar_key = f"avatars/{user_id}_avatar.jpg"
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
        url_avatar = await s3_client.get_file_url(avatar_key)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=profile_data.gender,
        date_of_birth=birth_date,
        info=profile_data.info,
        avatar=avatar_key
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=url_avatar
    )
