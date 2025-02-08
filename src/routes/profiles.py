
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fastapi import APIRouter, status, Depends, HTTPException

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from security.http import get_token
from database import get_db, UserModel, UserGroupModel, UserProfileModel, UserGroupEnum
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_name, validate_gender, validate_birth_date, validate_image

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
def create_profile(
        user_id: int,
        user_profile: ProfileRequestSchema = Depends(ProfileRequestSchema.from_form),
        db: Session = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        token: str = Depends(get_token),
) -> ProfileResponseSchema:

    try:
        decoded_token = jwt_manager.decode_access_token(token)
        data_user_id = decoded_token.get("user_id")
    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    try:
        validate_name(user_profile.first_name)
        validate_name(user_profile.last_name)
        validate_gender(user_profile.gender)
        validate_birth_date(user_profile.date_of_birth)
        validate_image(user_profile.avatar)
        if not user_profile.info or not user_profile.info.strip():
            raise ValueError("Info field empty.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    user = db.query(UserModel).filter(UserModel.id == data_user_id).first()
    if not data_user_id or (user_id != data_user_id and user.group.name != UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    profile = db.query(UserProfileModel).filter(UserProfileModel.id == user_id).first()
    if profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    try:
        contents = user_profile.avatar.file.read()
        file_name = f"avatars/{user_id}_avatar.jpg"
        s3_client.upload_file(file_name, contents)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=user_profile.first_name.lower(),
            last_name=user_profile.last_name.lower(),
            gender=user_profile.gender,
            date_of_birth=user_profile.date_of_birth,
            info=user_profile.info,
            avatar=file_name,
        )
        db.add(new_profile)
        db.commit()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation."
        )

    new_profile.avatar = s3_client.get_file_url(file_name)
    return ProfileResponseSchema.model_validate(new_profile)
