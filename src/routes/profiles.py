from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, UserProfileModel, get_db
from exceptions import TokenExpiredError
from schemas.profiles import ProfileRequestForm, ProfileResponseSchema
from security.http import get_token
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface
from validation import (
    validate_birth_date,
    validate_gender,
    validate_image,
    validate_name,
)

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201,
)
def profile(
    user_id: int,
    profile_form: ProfileRequestForm = Depends(ProfileRequestForm.as_form),
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
    storage: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        access_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")

    try:
        validate_name(profile_form.first_name)
        validate_name(profile_form.last_name)
        validate_gender(profile_form.gender)
        validate_birth_date(profile_form.date_of_birth)
        if not profile_form.info.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        validate_image(profile_form.avatar)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))

    token_user = (
        db.query(UserModel)
        .filter(UserModel.id == access_token.get("user_id"))
        .first()
    )

    if user_id != token_user.id and token_user.group.name.value != "admin":
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile.",
        )

    user = db.query(UserModel).filter_by(id=user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401, detail="User not found or not active."
        )

    profile = db.query(UserProfileModel).filter_by(user_id=user.id).first()
    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
        file_name = f"avatars/{user.id}_avatar.jpg"
        file_data = profile_form.avatar.file.read()
        storage.upload_file(file_name, file_data)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        first_name=profile_form.first_name.lower(),
        last_name=profile_form.last_name.lower(),
        gender=profile_form.gender,
        date_of_birth=profile_form.date_of_birth,
        info=profile_form.info,
        user_id=user.id,
        avatar=file_name,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {
        "id": profile.id,
        "user_id": user.id,
        "first_name": profile_form.first_name.lower(),
        "last_name": profile_form.last_name.lower(),
        "gender": profile_form.gender,
        "date_of_birth": profile_form.date_of_birth,
        "info": profile_form.info,
        "avatar": storage.get_file_url(file_name),
    }
