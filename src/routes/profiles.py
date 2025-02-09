from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileRequestForm
from security.http import get_token
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
def profile(
        user_id: int,
        access_token: str = Depends(get_token),
        profile_form: ProfileRequestForm = Depends(ProfileRequestForm.as_form),
        jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
        storage: S3StorageInterface = Depends(get_s3_storage_client),
        db: Session = Depends(get_db),
):
    try:
        jwt_manager.verify_access_token_or_raise(access_token)
        decoded_token = jwt_manager.decode_access_token(access_token)
    except BaseSecurityError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err)
        )
    token_user_id = decoded_token.get("user_id")

    try:
        if not profile_form.info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err)
        )

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

    db_profile = db.query(UserProfileModel).filter(UserProfileModel.user_id == db_user.id).first()
    if db_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    file_name = f"avatars/{user_id}_avatar.jpg"
    try:
        file_data = profile_form.avatar.file.read()
        storage.upload_file(file_name, file_data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    profile = UserProfileModel(
        first_name=profile_form.first_name.lower(),
        last_name=profile_form.last_name.lower(),
        gender=profile_form.gender,
        date_of_birth=profile_form.date_of_birth,
        info=profile_form.info,
        user_id=user_id,
        avatar=file_name,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return ProfileResponseSchema(
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=storage.get_file_url(file_name)
    )
