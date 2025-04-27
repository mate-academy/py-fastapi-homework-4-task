from fastapi import APIRouter, Depends, status, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from config import get_s3_storage_client
from crud import get_user_by_id
from database import UserProfileModel
from src.config import get_jwt_auth_manager
from src.schemas.profiles import UserCreate

from src.database import get_db
from storages import S3StorageInterface
from validation import validate_image

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=UserCreate)
async def user_profile_create(
    user_id: int,
    token: str = Depends(get_jwt_auth_manager().verify_access_token_or_raise),
    db: AsyncSession = Depends(get_db),
    avatar_file: UploadFile = None,
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    user = await get_user_by_id(user_id, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if str(user.activation_token) != token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    if user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    if avatar_file:
        validate_image(avatar_file)

    try:
        file_info = await avatar_file.read()
        await s3_client.upload_file(f"{user_id}.filename", file_info)
    except Exception:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        gender=user.gender,
        date_of_birth=user.date_of_birth,
        info=user.info,
        avatar=s3_client.get_file_url("{user_id}.filename"),
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(user.profile)

    return user.profile
