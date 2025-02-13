from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from schemas.profiles import ProfileSchema, ProfileResponseSchema
from sqlalchemy.orm import Session
from botocore.exceptions import ClientError
from database import get_db
from config import get_jwt_auth_manager, get_settings, BaseAppSettings
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token
from jose import JWTError, ExpiredSignatureError

from database.models.accounts import UserModel, UserProfileModel

from config.dependencies import get_s3_storage_client
from storages import S3StorageInterface, s3

from exceptions.security import TokenExpiredError
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

from exceptions.storage import S3FileUploadError

from database.models.accounts import UserGroupModel

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileSchema,
    summary="Creation user's profile",
    description="This endpoint is responsible for handling user profile creation.",
    responses={
        201: {
            "description": "Profile created successfully.",
        },
        400: {
            "description": "Bad Request.",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a profile."}
                }
            }
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "examples": {
                        "Missing Token": {
                            "summary": "Missing Token",
                            "value": {"detail": "Authorization header is missing"}
                        },
                        "Invalid Token Format": {
                            "summary": "Invalid Token Format",
                            "value": {"detail": "Invalid Authorization header format. Expected 'Bearer <token>'"}
                        },
                        "Expired Token": {
                            "summary": "Expired Token",
                            "value": {"detail": "Token has expired."}
                        },
                        "User Not Found or Not Active": {
                            "summary": "User Not Found or Not Active",
                            "value": {"detail": "User not found or not active."}
                        },
                    }
                }
            }
        },
        403: {
            "description": "Unauthorized Profile Creation",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to edit this profile."
                    }
                }
            }
        },
        500: {
            "description": "Avatar Upload Failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to upload avatar. Please try again later."}
                }
            }
        },
    },
    status_code=201,
)
def create_profile(
        user_id: int,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(None),
        token: str = Depends(get_token),
        db: Session = Depends(get_db),
        settings: BaseAppSettings = Depends(get_settings),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),

) -> ProfileResponseSchema:

    try:
        payload = jwt_manager.decode_access_token(token)
        user_token_id = payload["user_id"]
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    existing_profile = db.query(UserProfileModel).filter(UserProfileModel.user_id == user_token_id).first()
    if existing_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    user = db.query(UserModel).filter(UserModel.id == user_token_id).first()

    if user:
        is_active = user.is_active
        if not is_active:
            raise HTTPException(status_code=401, detail="User not found or not active.")
        user_group_id = user.group_id
        user_group = db.query(UserGroupModel).filter(UserGroupModel.id == user_group_id).first()
        if user_token_id != user_id and user_group.name != "admin":
            raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    # Validations
    try:
        validate_name(first_name)
        validate_name(last_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        validate_gender(gender)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        validate_birth_date(date_of_birth)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        if len(" ".join(info.split())) == 0:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="Info field cannot be empty or contain only spaces.")

    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Validate & Save avatar
    if not avatar.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File is not an image")

    if avatar.size > 1 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 1MB limit")

    avatar_key = f"avatars/{user_id}_avatar.jpg"

    file_data = avatar.file.read()

    try:
        s3_client.upload_file(
            file_name=avatar_key, file_data=file_data
        )

        avatar_url = s3_client.get_file_url(file_name=avatar_key)

        # Create new_profile
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=first_name.lower(),
            last_name=last_name.lower(),
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar_url,
        )

        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        return ProfileResponseSchema.model_validate(new_profile)

    except ClientError:
        raise HTTPException(status_code=422, detail="Failed to upload avatar.")
    except S3FileUploadError:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")
