from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import ExpiredSignatureError
from sqlalchemy.orm import Session
from starlette import status

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserProfileModel, get_db, UserModel, UserGroupEnum
from exceptions import InvalidTokenError, BaseS3Error, TokenExpiredError
from schemas.profiles import ProfileRequestForm, ProfileResponseSchema
from security.http import get_token
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface
router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201
)
def profile(
        request: Request,
        user_id: int,
        profile_form: Optional[ProfileRequestForm] = Depends(ProfileRequestForm.as_form),
        db: Session = Depends(get_db),
        manager: JWTAuthManager = Depends(get_jwt_auth_manager),
        storage: S3StorageInterface = Depends(get_s3_storage_client),
):
    token = get_token(request)
    try:
        decoded_jwt = manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    user = db.query(UserModel).filter_by(id=user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )
    if user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    request_user = db.query(UserModel).filter_by(id=decoded_jwt.get("user_id")).first()

    if (
        request_user != user
        and request_user.group.name != UserGroupEnum.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    try:
        file_name = f"avatars/{user.id}_avatar.jpg"
        file_data = profile_form.avatar.file.read()
        storage.upload_file(file_name, file_data)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )
    profile = UserProfileModel(
        first_name=profile_form.first_name.lower(),
        last_name=profile_form.last_name.lower(),
        gender=profile_form.gender,
        date_of_birth=profile_form.date_of_birth,
        info=profile_form.info,
        user_id=user.id,
        avatar=file_name
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return ProfileResponseSchema(**profile.__dict__)
