from datetime import date
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Form,
    UploadFile,
    File
)
from sqlalchemy.orm import Session

from database import get_db
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from security.interfaces import JWTAuthManagerInterface
from config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from exceptions.security import TokenExpiredError, InvalidTokenError
from storages.interfaces import S3StorageInterface
from database.models.accounts import UserModel, UserProfileModel
from security.http import get_token
from database.models.accounts import UserGroupEnum

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201
)
async def create_profile(
        user_id: int,
        request: Request,
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: Session = Depends(get_db),
        info: Optional[str] = Form(None),
        first_name: Optional[str] = Form(None),
        last_name: Optional[str] = Form(None),
        gender: Optional[str] = Form(None),
        date_of_birth: Optional[date] = Form(None),
        avatar: Optional[UploadFile] = File(None),
):
    token = get_token(request)

    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired."
        )

    request_user = db.query(UserModel).filter(UserModel.id == payload["user_id"]).first()
    if payload["user_id"] != user_id and request_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile."
        )

    data = ProfileRequestSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar
    )

    user = db.query(UserModel).filter(UserModel.id == user_id, UserModel.is_active).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    user_profile = db.query(UserProfileModel).filter(UserProfileModel.user_id == user_id).first()
    if user_profile:
        raise HTTPException(
            status_code=400,
            detail="User already has a profile."
        )

    if data.avatar:
        try:
            file_name = f"avatars/{user_id}_avatar.jpg"
            file_data = await data.avatar.read()
            s3_client.upload_file(file_name, file_data)
            avatar_url = s3_client.get_file_url(file_name)

        except Exception:
            raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    first_name = data.first_name
    last_name = data.last_name
    gender = data.gender

    profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower() if first_name else first_name,
        last_name=last_name.lower() if last_name else last_name,
        gender=gender.lower() if gender else gender,
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=avatar_url
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile
