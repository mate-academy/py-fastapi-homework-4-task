from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    status,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    Form,
)

from database import get_db, UserModel, UserProfileModel
from config import (
    get_jwt_auth_manager,
    get_s3_storage_client
)
from pydantic import ValidationError
from schemas import ProfileResponseSchema
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session

from security.interfaces import JWTAuthManagerInterface
from security.http import get_token

from exceptions import (
    BaseSecurityError
)

from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile",
    response_model=ProfileResponseSchema,
    summary="Profile Creation",
    description="Authorization: Requires a valid Bearer token "
                "in the Authorization header",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "Bad Request",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a profile."}
                }
            },
        },
        401: {
            "description": "Invalid Authorization header format.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid Authorization header format. "
                                  "Expected 'Bearer <token>"
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - Lack of permission.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission "
                                  "to edit this profile."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to upload avatar. "
                                  "Please try again later"
                    }
                }
            },
        },
    },
)
async def create_profile(
        request: Request,
        user_id: int,
        first_name: Optional[str] = Form(None),
        last_name: Optional[str] = Form(None),
        gender: Optional[str] = Form(None),
        date_of_birth: Optional[str] = Form(None),
        info: Optional[str] = Form(None),
        avatar: UploadFile = File(None),
        db: Session = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    # GET ACCESS TOKEN
    access_token = get_token(request)
    # Verify ACCESS TOKEN
    try:
        decode_access_token = jwt_manager.decode_access_token(access_token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    db_user = (
        db.query(UserModel)
        .filter(UserModel.id == decode_access_token["user_id"])
        .first()
    )
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or not active.",
        )

    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if decode_access_token["user_id"] != user_id and db_user.group_id != 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # IF profile exist
    exist_profile = (
        db.query(UserProfileModel)
        .filter_by(user_id=user_id)
        .first()
    )
    if exist_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    # CREATE new user's profile
    file_name = f"avatars/{user_id}_avatar.jpg"
    file_data = await avatar.read()

    if not file_data:
        raise HTTPException(
            status_code=400,
            detail="Failed to read file data."
        )
    s3_client.upload_file(file_name, file_data)
    avatar_url = s3_client.get_file_url(file_name)

    if isinstance(date_of_birth, str):
        date_of_birth = datetime.strptime(date_of_birth, "%Y-%m-%d").date()

    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=first_name.lower() if first_name else None,
            last_name=last_name.lower() if last_name else None,
            gender=gender.upper() if gender else None,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar_url or None,
        )

        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        response = ProfileResponseSchema.model_validate(new_profile)
        return response

    except ValidationError as err:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(err))

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="Invalid input data.")

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )
