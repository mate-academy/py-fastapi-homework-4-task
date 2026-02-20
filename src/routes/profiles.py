from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, File
from sqlalchemy.orm import Session
from starlette import status

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel
from database.models.accounts import GenderEnum
from exceptions import (
    TokenExpiredError,
    S3ConnectionError,
    S3FileUploadError,
)
from schemas.profiles import ProfileResponseSchema
from security.http import get_token
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface
from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
    validate_image,
)

router = APIRouter()


@router.post(
    "/users/{user_id}/profile",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    authorization: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManager = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        payload = jwt_manager.decode_access_token(authorization)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )

    try:
        validate_name(first_name)
        validate_name(last_name)
        validate_birth_date(date_of_birth)
        validate_gender(gender)

        if not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")

        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )

    user = db.query(UserModel).filter(UserModel.id == payload.get("user_id")).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if user.id != user_id and user.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    existing_profile = user.profile
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )
    avatar_url = None
    if avatar:
        try:
            file_name = f"avatars/{user_id}_avatar.jpg"
            s3_client.upload_file(file_name, avatar.file.read())
            avatar_url = s3_client.get_file_url(file_name)
        except (S3ConnectionError, S3FileUploadError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later.",
            )

            gender_enum = GenderEnum(gender)

            new_profile = UserProfileModel(
                user_id=user_id,
                first_name=first_name.lower(),
                last_name=last_name.lower(),
                gender=gender_enum.value,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar_url,
            )
            db.add(new_profile)
            db.commit()
            db.refresh(new_profile)

            return ProfileResponseSchema(
                id=new_profile.id,
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                gender=new_profile.gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar_url,
            )
