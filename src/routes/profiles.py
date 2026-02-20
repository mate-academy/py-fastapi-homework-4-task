from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
import validation
from exceptions import BaseSecurityError, S3FileUploadError
from config import get_jwt_auth_manager, get_s3_storage_client
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from security.http import get_token
from security.token_manager import JWTAuthManager
from sqlalchemy.orm import selectinload
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
        user_id: int,
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
        profile_data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        decode_token = jwt_manager.decode_access_token(token)
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    try:
        validation.validate_name(profile_data.first_name)
        validation.validate_name(profile_data.last_name)
        validation.validate_gender(profile_data.gender)
        validation.validate_birth_date(profile_data.date_of_birth)
        if not profile_data.info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        validation.validate_image(profile_data.avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    db_user = result.scalars().first()
    if not (db_user and db_user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    result_two = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    db_profile = result_two.scalar_one_or_none()
    if db_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    token_user_id = decode_token["user_id"]
    request_result = await db.execute(select(UserModel).options(selectinload(UserModel.group)).where(
        UserModel.id == token_user_id
    ))
    request_user = request_result.scalar_one_or_none()
    if user_id != token_user_id and request_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    try:
        file_name = f"avatars/{user_id}_avatar.jpg"
        file_data = profile_data.avatar.file.read()
        await s3_client.upload_file(file_name, file_data)

        profile = UserProfileModel(
            first_name=profile_data.first_name.lower(),
            last_name=profile_data.last_name.lower(),
            gender=profile_data.gender,
            date_of_birth=profile_data.date_of_birth,
            info=profile_data.info,
            avatar=file_name,
            user_id=db_user.id,
        )

        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    except (SQLAlchemyError, S3FileUploadError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=await s3_client.get_file_url(file_name)
    )
