from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, UserModel, UserProfileModel, UserGroupEnum, UserGroupModel
from database.models.accounts import GenderEnum
from config import get_jwt_auth_manager, get_s3_storage_client
from schemas.profiles import ProfileCreateRequestSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from exceptions.storage import S3FileUploadError, S3ConnectionError

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    data: ProfileCreateRequestSchema = Depends(ProfileCreateRequestSchema.as_form),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    try:
        decoded = jwt_manager.decode_access_token(token)
    except Exception as error:
        # Map security-related errors to 401 with exact message
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))

    current_user_id = decoded.get("user_id")

    # Authorization: only self or admin can create a profile for another user
    stmt_current = select(UserModel).where(UserModel.id == current_user_id)
    result_current = await db.execute(stmt_current)
    current_user = result_current.scalars().first()

    stmt_target = select(UserModel).where(UserModel.id == user_id)
    result_target = await db.execute(stmt_target)
    target_user = result_target.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    is_admin = False
    if current_user:
        stmt_group = select(UserGroupModel.name).where(UserGroupModel.id == current_user.group_id)
        res_group = await db.execute(stmt_group)
        group_name = res_group.scalar()
        is_admin = group_name == UserGroupEnum.ADMIN
    if current_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    # Check if profile already exists
    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result_profile = await db.execute(stmt_profile)
    existing_profile = result_profile.scalars().first()
    if existing_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    # Upload avatar to S3
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    try:
        file_bytes = data.avatar.file.read()
        await s3_client.upload_file(avatar_key, file_bytes)
        avatar_url = await s3_client.get_file_url(avatar_key)
    except (S3FileUploadError, S3ConnectionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Create profile in DB
    profile = UserProfileModel(
        user_id=user_id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=GenderEnum(data.gender),
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=avatar_key,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender.value,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
