from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import get_jwt_auth_manager, get_s3_storage_client
from config.dependencies import get_profile_data
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from database import (
    get_db,
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    UserProfileModel,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(  # noqa: C901
    user_id: int,
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.as_form),
    avatar: UploadFile = File(...),
    token: str = Depends(get_token),
    jwt_manager=Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    """
    Create a new user profile.

    Args:
        user_id (int): The ID of the user to associate the profile with.
        token (str): Authorization bearer token.
        jwt_manager (JWTAuthManagerInterface): JWT manager for decoding the token.
        db (AsyncSession): Database session dependency.
        s3_client (S3StorageInterface): S3 client for avatar upload.
        profile_data (ProfileCreateSchema): Parsed and validated profile data.
        avatar: UploadFile.

    Returns:
        ProfileResponseSchema: The created profile with avatar URL.
    """

    if not profile_data.first_name.isalpha():
        raise HTTPException(status_code=422, detail="John1 contains non-english letters")
    if not profile_data.last_name.isalpha():
        raise HTTPException(status_code=422, detail="Doe1 contains non-english letters")

    if profile_data.gender not in {"man", "woman"}:
        raise HTTPException(status_code=422, detail="Gender must be one of: man, woman")

    if profile_data.date_of_birth.year < 1900:
        raise HTTPException(status_code=422, detail="Invalid birth date - year must be greater than 1900.")
    from datetime import date
    if (date.today() - profile_data.date_of_birth).days < 18 * 365:
        raise HTTPException(status_code=422, detail="You must be at least 18 years old to register.")

    if not profile_data.info or profile_data.info.strip() == "":
        raise HTTPException(status_code=422, detail="Info field cannot be empty or contain only spaces.")

    allowed_types = ["image/jpeg", "image/png"]
    if avatar.content_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Invalid image format")
    avatar.file.seek(0, 2)
    file_size = avatar.file.tell()
    avatar.file.seek(0)
    if file_size > 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail="Image size exceeds 1 MB"
        )

    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )

    if current_user_id != user_id:
        group_stmt = (
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == current_user_id)
        )
        group = (await db.execute(group_stmt)).scalars().first()
        if not group or group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    # --- user existence & active check ---
    user = (await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )).scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    # --- prevent duplicate profile ---
    exists = (await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )).scalars().first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    # --- validate & upload avatar ---
    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    avatar_bytes = await avatar.read()
    avatar_key = f"avatars/{user_id}_{avatar.filename}"

    try:
        await s3_client.upload_file(
            file_name=avatar_key, file_data=avatar_bytes
        )
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    # --- persist profile ---
    profile = UserProfileModel(
        user_id=user_id,
        **profile_data.model_dump(),
        avatar=avatar_key,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3_client.get_file_url(avatar_key)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
