import asyncio

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
    token = request.headers.get("Authorization")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )

    parts_of_token = token.split()
    if parts_of_token[0] != "Bearer" or len(parts_of_token) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
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
    try:
        data = jwt_auth_manager.decode_access_token(parts_of_token[1])
        user = db.query(UserModel).filter_by(id=data["user_id"]).first()

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

        profile = db.query(UserProfileModel).filter_by(user_id=user_id).first()

        if profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a profile."
            )
        profile = UserProfileModel()

        avatar_name = f"avatars/{user_id}_avatar.jpg"
        avatar = asyncio.run(data_profile.avatar.read())
        try:
            s3_client.upload_file(avatar_name, avatar)
            avatar_url = s3_client.get_file_url(avatar_name)
        except S3FileUploadError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later."
            )

        profile.user_id = user_id
        profile.first_name = data_profile.first_name.lower()
        profile.last_name = data_profile.last_name.lower()
        profile.gender = data_profile.gender
        profile.date_of_birth = data_profile.date_of_birth
        profile.info = data_profile.info
        profile.avatar = avatar_name

        db.add(profile)
        db.commit()

        profile.avatar = avatar_url

        return profile
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
