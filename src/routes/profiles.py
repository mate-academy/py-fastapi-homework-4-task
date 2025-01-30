from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
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


def validate_profile_form(profile_form: ProfileRequestForm):
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


def get_current_user(db: Session, token: str, jwt_manager: JWTAuthManager) -> UserModel:
    try:
        token_data = jwt_manager.decode_access_token(token)
        user = db.query(UserModel).filter_by(id=token_data.get("user_id")).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )


def check_permissions(current_user: UserModel, user_id: int):
    if user_id != current_user.id and current_user.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )


def upload_avatar(storage: S3StorageInterface, user_id: int, avatar: UploadFile) -> str:
    file_name = f"avatars/{user_id}_avatar.jpg"
    try:
        file_data = avatar.file.read()
        storage.upload_file(file_name, file_data)
        return file_name
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )


@router.post("/users/{user_id}/profile/", status_code=status.HTTP_201_CREATED)
def create_profile(
    user_id: int,
    profile_form: ProfileRequestForm = Depends(ProfileRequestForm.as_form),
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
    storage: S3StorageInterface = Depends(get_s3_storage_client),
):
    validate_profile_form(profile_form)

    current_user = get_current_user(db, token, jwt_manager)

    check_permissions(current_user, user_id)

    if db.query(UserProfileModel).filter_by(user_id=user_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    avatar_file_name = upload_avatar(storage, user_id, profile_form.avatar)

    profile = UserProfileModel(
        first_name=profile_form.first_name.lower(),
        last_name=profile_form.last_name.lower(),
        gender=profile_form.gender,
        date_of_birth=profile_form.date_of_birth,
        info=profile_form.info,
        user_id=user_id,
        avatar=avatar_file_name,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "gender": profile.gender,
        "date_of_birth": profile.date_of_birth,
        "info": profile.info,
        "avatar": storage.get_file_url(avatar_file_name)
    }
