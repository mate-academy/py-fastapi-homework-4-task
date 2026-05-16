from datetime import date
from fastapi import (
    APIRouter,
    Form,
    UploadFile,
    File,
    Depends,
    status,
    HTTPException
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import get_jwt_auth_manager, get_s3_storage_client
from database.models.accounts import GenderEnum
from exceptions import TokenExpiredError, S3FileUploadError
from security.http import get_token
from database import get_db, UserModel, UserProfileModel
from schemas.profiles import (
    ProfileResponseSchema,
    validate_name_field,
    validate_birth_date_field,
    validate_gender_field,
    validate_info_field,
    validate_avatar
)
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(default=""),
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    token: str = Depends(get_token),
):

    # Validation token
    try:
        token_user_id = jwt_manager.decode_access_token(token)["user_id"]
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    # Checking access rights
    if token_user_id != user_id:
        query_group = await db.execute(select(UserModel).where(UserModel.id == token_user_id))
        token_user = query_group.scalars().first()
        if token_user.group_id != 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    # Verifying user existence and activity
    query_user = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = query_user.scalars().first()
    if not user or user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    # Check if the profile already exists
    query_profile = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    profile = query_profile.scalars().first()
    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # Form data validation
    file_data = await avatar.read()
    avatar.file.seek(0)

    try:
        validate_name_field(first_name)
        validate_name_field(last_name)
        validate_gender_field(gender)
        validate_birth_date_field(date_of_birth)
        validate_info_field(info)
        validate_avatar(avatar)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Uploading an avatar to S3
    try:
        file_name = f"avatars/{user_id}_avatar.jpg"
        await s3_client.upload_file(file_name=file_name, file_data=file_data)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Saving the profile in the database
    user_profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower(),
        last_name=last_name.lower(),
        gender=GenderEnum(gender),
        date_of_birth=date_of_birth,
        info=info,
        avatar=file_name,
    )

    db.add(user_profile)
    await db.commit()
    await db.refresh(user_profile)
    avatar_url = await s3_client.get_file_url(file_name=file_name)

    # Return response
    return ProfileResponseSchema(
        id=user_profile.id,
        user_id=user_profile.user_id,
        first_name=user_profile.first_name,
        last_name=user_profile.last_name,
        gender=user_profile.gender,
        date_of_birth=user_profile.date_of_birth,
        info=user_profile.info,
        avatar=avatar_url,
    )
