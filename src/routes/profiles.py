from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from src.config import get_jwt_auth_manager, get_s3_storage_client
from src.database import UserProfileModel, get_db, UserModel
from src.exceptions import TokenExpiredError
from src.schemas.profiles import ProfileRequestForm, ProfileResponseSchema
from src.security.http import get_token
from src.security.token_manager import JWTAuthManager
from src.storages import S3StorageInterface
from src.validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201
)
def profile(
        user_id: int,
        db: Session = Depends(get_db),
        token: str = Depends(get_token),
        manager: JWTAuthManager = Depends(get_jwt_auth_manager),
        storage: S3StorageInterface = Depends(get_s3_storage_client),
        profile_form: ProfileRequestForm = Depends(
            ProfileRequestForm.as_form
        ),
):
    try:
        decoded_access_token = manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    try:
        validate_name(profile_form.first_name)
        validate_name(profile_form.last_name)
        validate_birth_date(profile_form.date_of_birth)
        validate_gender(profile_form.gender)
        if not profile_form.info.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        validate_image(profile_form.avatar)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    user = db.query(UserModel).filter(
        UserModel.id == decoded_access_token.get("user_id")
    ).first()

    if not user or user.is_active is False:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    if user_id != user.id and user.group.name != "admin":
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile."
        )
    profile_exist = db.query(UserProfileModel).filter(
        UserProfileModel.user_id == user_id
    ).first()
    if profile_exist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )
    try:
        filename = f"avatars/{user_id}_avatar.jpg"
        contents = profile_form.avatar.file.read()
        storage.upload_file(filename, contents)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )
    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=profile_form.first_name.lower(),
            last_name=profile_form.last_name.lower(),
            gender=profile_form.gender,
            date_of_birth=profile_form.date_of_birth,
            info=profile_form.info,
            avatar=filename,
        )
        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)
        return {
            "id": new_profile.id,
            "user_id": new_profile.user_id,
            "first_name": new_profile.first_name,
            "last_name": new_profile.last_name,
            "gender": new_profile.gender,
            "date_of_birth": new_profile.date_of_birth,
            "info": new_profile.info,
            "avatar": storage.get_file_url(filename),
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile. Please try again later."
        )
