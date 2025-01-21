from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from exceptions import (
    S3ConnectionError,
    S3FileUploadError
)

from schemas.profiles import ProfileSchema, ProfileResponseSchema
from config.dependencies import get_s3_storage_client
from storages.interfaces import S3StorageInterface
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token
from database import get_db
from database.models.accounts import UserModel, UserProfileModel
from config.dependencies import get_jwt_auth_manager


router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
        user_id: int,
        profile_data: ProfileSchema,
        token: str = Depends(get_token),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        db: Session = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    data = jwt_manager.decode_access_token(token)

    is_expired = data.get("exp") <= 0
    if is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    current_user = db.query(UserModel).filter_by(id=data.get("user_id")).first()

    if user_id != current_user.id and current_user.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    user = db.query(UserModel).filter_by(id=user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    profile = db.query(UserProfileModel).filter_by(user_id=user.id).first()
    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        await s3_client.upload_file(profile_data.first_name, profile_data.avatar)
        file_url = s3_client.get_file_url(profile_data.first_name)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        avatar=file_url,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        user_id=user.id
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    return new_profile
