from fastapi import APIRouter, status, Depends, HTTPException

from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema

from security.http import get_token
from security.interfaces import JWTAuthManagerInterface

from database import get_db, UserModel, UserGroupEnum, UserProfileModel

from config.dependencies import get_jwt_auth_manager, get_s3_storage_client

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from storages.interfaces import S3StorageInterface

from exceptions.security import BaseSecurityError
from exceptions.storage import S3FileUploadError

import validation

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
def create_profile(
    user_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: Session = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    profile_data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form)
) -> ProfileResponseSchema:

    try:
        decoded_token = jwt_manager.decode_access_token(token)
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

    token_user_id = decoded_token["user_id"]
    request_user = db.query(UserModel).filter(UserModel.id == token_user_id).first()
    if user_id != token_user_id and request_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not db_user or not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    db_profile = db.query(UserProfileModel).filter(UserProfileModel.user_id == user_id).first()
    if db_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        file_name = f"avatars/{db_user.id}_avatar.jpg"
        file_data = profile_data.avatar.file.read()
        s3_client.upload_file(file_name, file_data)

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
        db.commit()
        db.refresh(profile)

    except (SQLAlchemyError, S3FileUploadError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=s3_client.get_file_url(profile.avatar)
    )
