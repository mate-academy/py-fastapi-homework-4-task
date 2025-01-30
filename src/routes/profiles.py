from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, UserProfileModel, get_db
from exceptions import BaseSecurityError, InvalidTokenError, S3ConnectionError, \
    S3FileUploadError, TokenExpiredError
from schemas import ProfileRequestForm
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_birth_date, validate_gender, validate_image, \
    validate_name

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    summary="Create a user profile",
    description=(
            "<h3>This endpoint allows creating a profile for a specific user. "
            "The profile includes personal information such as name, gender, date of birth, "
            "and an avatar image. The avatar will be stored in MinIO storage.<h3>"
            "<p>Note: Users can only create profiles for themselves unless they have admin privileges.</p>"
    ),
    responses={
        status.HTTP_201_CREATED: {"description": "Profile created successfully."},
        status.HTTP_400_BAD_REQUEST: {
            "description": "Bad request. Profile not created.",
            "content": {
                "application/json": {
                    "examples": {
                        "profile_exists": {
                            "summary": "Profile Already Exists",
                            "value": {"detail": "User already has a profile."},
                        }
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Unauthorized",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_token": {
                            "summary": "Missing Token",
                            "value": {"detail": "Authorization header is missing"},
                        },
                        "invalid_token": {
                            "summary": "Invalid Token",
                            "value": {
                                "detail": "Invalid Authorization header format. Expected 'Bearer <token>'"},
                        },
                        "expired_token": {
                            "summary": "Expired Token",
                            "value": {"detail": "Token has expired."},
                        },
                        "user_not_found": {
                            "summary": "User Not Found",
                            "value": {"detail": "User not found or not active."},
                        },
                    }
                }
            },
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Forbidden",
            "content": {
                "application/json": {"example": {
                    "detail": "You don't have permission to edit this profile."}}
            },
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_name": {
                            "summary": "Invalid Name",
                            "value": {"detail": "Name contains non-english letters"},
                        },
                        "invalid_gender": {
                            "summary": "Invalid Gender",
                            "value": {"detail": "Gender must be one of: man, woman"},
                        },
                        "invalid_birth_date": {
                            "summary": "Invalid Birth Date",
                            "value": {
                                "detail": "You must be at least 18 years old to register."},
                        },
                        "invalid_image": {
                            "summary": "Invalid Image",
                            "value": {"detail": "Image size exceeds 1 MB"},
                        },
                    }
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "examples": {
                        "storage_connection": {
                            "summary": "Storage Connection Error",
                            "value": {
                                "detail": "Failed to connect to storage service."},
                        },
                        "upload_error": {
                            "summary": "File Upload Error",
                            "value": {
                                "detail": "Failed to upload avatar. Please try again later."},
                        },
                    }
                }
            },
        },
    },
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
        request: Request,
        user_id: int,
        profile_form: ProfileRequestForm = Depends(ProfileRequestForm.as_form),
        db: Session = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        storage: S3StorageInterface = Depends(get_s3_storage_client),
) -> dict:
    try:
        get_token(request)
    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    try:
        token_data = jwt_manager.decode_access_token(token)
        token_data.get("user_id")
    except (TokenExpiredError, InvalidTokenError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))

    try:
        if not profile_form.info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")

        validate_name(profile_form.first_name)
        validate_name(profile_form.last_name)
        validate_gender(profile_form.gender)
        validate_birth_date(profile_form.date_of_birth)
        validate_image(profile_form.avatar)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(error))

    existing_user = db.query(UserModel).filter_by(id=token_data.get("user_id"),
                                                  is_active=True).first()

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if user_id != existing_user.id and not existing_user.has_group("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    existing_profile = db.query(UserProfileModel).filter_by(user_id=user_id).first()

    if existing_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="User already has a profile.")

    try:
        avatar_filename = f"avatars/{user_id}_avatar.jpg"
        file_data = profile_form.avatar.file.read()
        storage.upload_file(avatar_filename, file_data)
    except S3ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to storage service.",
        )
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        first_name=profile_form.first_name.lower(),
        last_name=profile_form.last_name.lower(),
        gender=profile_form.gender,
        date_of_birth=profile_form.date_of_birth,
        info=profile_form.info,
        user_id=user_id,
        avatar=avatar_filename,
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    return {
        "id": new_profile.id,
        "user_id": user_id,
        "first_name": profile_form.first_name.lower(),
        "last_name": profile_form.last_name.lower(),
        "gender": profile_form.gender,
        "date_of_birth": profile_form.date_of_birth,
        "info": profile_form.info,
        "avatar": storage.get_file_url(avatar_filename),
    }
