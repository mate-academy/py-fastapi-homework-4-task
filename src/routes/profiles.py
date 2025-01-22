import asyncio
from typing import Type

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from config import get_s3_storage_client, get_jwt_auth_manager
from exceptions import TokenExpiredError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileRequestForm
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from database import get_db, UserModel, UserProfileModel
from validation import validate_name, validate_gender, validate_image, validate_birth_date
from validation.profile import validate_info

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
        request: Request,
        user_id: int,
        data_profile: ProfileRequestForm = Depends(ProfileRequestForm.as_form),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        jwt_auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: Session = Depends(get_db),
):
    token = _extract_token(request)
    _validate_profile_data(data_profile)

    try:
        user_data = jwt_auth_manager.decode_access_token(token)
        _get_user_from_db(db, user_data["user_id"], user_id)

        _check_existing_profile(db, user_id)

        avatar_name = f"avatars/{user_id}_avatar.jpg"
        avatar_content = asyncio.run(data_profile.avatar.read())
        _upload_avatar_to_s3(s3_client, avatar_name, avatar_content)

        profile = _create_user_profile(db, user_id, data_profile, avatar_name)
        profile.avatar = s3_client.get_file_url(avatar_name)

        return profile

    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )


def _extract_token(request: Request) -> str:

    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )
    parts = token.split()
    if parts[0] != "Bearer" or len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
    return parts[1]


def _validate_profile_data(data_profile: ProfileRequestForm):

    try:
        validate_name(data_profile.first_name)
        validate_name(data_profile.last_name)
        validate_gender(data_profile.gender)
        validate_birth_date(data_profile.date_of_birth)
        validate_info(data_profile.info)
        validate_image(data_profile.avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


def _get_user_from_db(db: Session, token_user_id: int, user_id: int) -> Type[UserModel] | None:

    user = db.query(UserModel).filter_by(id=token_user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )
    if user.group_id != 3 and user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )
    return user


def _check_existing_profile(db: Session, user_id: int):

    if db.query(UserProfileModel).filter_by(user_id=user_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )


def _upload_avatar_to_s3(s3_client: S3StorageInterface, avatar_name: str, avatar_content: bytes):

    try:
        s3_client.upload_file(avatar_name, avatar_content)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )


def _create_user_profile(db: Session, user_id: int, data_profile: ProfileRequestForm,
                         avatar_name: str) -> UserProfileModel:

    profile = UserProfileModel(
        user_id=user_id,
        first_name=data_profile.first_name.lower(),
        last_name=data_profile.last_name.lower(),
        gender=data_profile.gender,
        date_of_birth=data_profile.date_of_birth,
        info=data_profile.info,
        avatar=avatar_name,
    )
    db.add(profile)
    db.commit()
    return profile
