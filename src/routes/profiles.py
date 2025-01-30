from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserProfileModel, get_db, UserModel
from exceptions import TokenExpiredError
from schemas.profiles import ProfileRequestForm
from security.http import get_token
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface
from validation.profile import validate_name, validate_image, validate_gender, validate_birth_date

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    status_code=201
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
        data = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    try:
        validate_name(profile_form.first_name)
        validate_name(profile_form.last_name)
        validate_gender(profile_form.gender)
        validate_birth_date(profile_form.date_of_birth)
        if not profile_form.info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        validate_image(profile_form.avatar)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err)
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
        file_name = f"avatars/{user.id}_avatar.jpg"
        file_data = profile_form.avatar.file.read()
        storage.upload_file(file_name, file_data)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

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
        "avatar": storage.get_file_url(file_name)
    }
