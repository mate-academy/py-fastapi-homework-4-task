from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import TokenExpiredError
from security.http import get_token
from schemas.profiles import ProfileResponseSchema, ProfileRequestForm
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface
from validation import validate_name, validate_birth_date, validate_gender, validate_image

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201,
)
def profile(
        user_id: int,
        db: Session = Depends(get_db),
        token: str = Depends(get_token),
        manager: JWTAuthManager = Depends(get_jwt_auth_manager),
        storage: S3StorageInterface = Depends(get_s3_storage_client),
        profile_form: ProfileRequestForm = Depends(
            ProfileRequestForm.as_form
        )):
    try:
        decoded_access_token = manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    try:
        validate_name(profile_form.first_name)
        validate_name(profile_form.last_name)
        validate_birth_date(profile_form.date_of_birth)
        validate_gender(profile_form.gender)

        if not profile_form.info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        validate_image(profile_form.avatar)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    user = db.query(UserModel).filter(UserModel.id == decoded_access_token.get("user_id")).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    if user.id != user_id and user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You don't have permission to edit this profile.")

    exists = db.query(UserProfileModel).filter(UserProfileModel.user_id == user_id).first()

    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    try:
        file = f"avatars/{user_id}_avatar.jpg"
        content = profile_form.avatar.file.read()
        storage.upload_file(file, content)
        avatar_url = storage.get_file_url(file)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to upload avatar. Please try again later.")

    try:
        profile = UserProfileModel(
            user_id=user_id,
            first_name=profile_form.first_name.lower(),
            last_name=profile_form.last_name.lower(),
            gender=profile_form.gender,
            date_of_birth=profile_form.date_of_birth,
            info=profile_form.info,
            avatar=file
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        return profile

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create profile. Please try again later.")
