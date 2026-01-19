from database.models.accounts import UserProfileModel, UserModel

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_s3_storage_client
from database import get_db
from exceptions import TokenExpiredError, InvalidTokenError

from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from storages import S3StorageInterface
from security.token_manager import decode_access_token


router = APIRouter()

# Write your code here
@router.post("/users/{user_id}/profile/",
             response_model=ProfileResponseSchema,
             status_code=status.HTTP_201_CREATED,
             )
async def create_profile(
        user_id: int,
        profile_data: ProfileRequestSchema,
        authorization: str = Header(None),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED
                            ,detail="Authorization header is missing")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid Authorization header format. Expected 'Bearer <token>'")
    token = authorization.split(" ")[1]
    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    if payload["role"] != "admin" and payload["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401,
                            detail="User not found or not active.")

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    existing_profile = result.scalar_one_or_none()
    if existing_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    avatar_url = None
    if profile_data.avatar:
        try:
            avatar_url = await s3_client.upload_file(
                file_bytes=profile_data.avatar,
                file_name=f"{user_id}_avatar.jpg",
                folder="avatars"
            )
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return ProfileResponseSchema.model_validate(new_profile)
