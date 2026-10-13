from jose import ExpiredSignatureError, JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status, Header
from schemas.profiles import ProfileResponseSchema, ProfileSchema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from storages import S3StorageClient
from security.token_manager import JWTAuthManagerInterface
from config import get_s3_storage_client
from security.dependencies import get_jwt_auth_manager

from database import (
    get_db,
    UserModel,
    UserProfileModel,
)

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    description="Create user profile",
    status_code=status.HTTP_201_CREATED,
)
async def profile_user(
    user_id: int,
    user_data: ProfileSchema = Depends(ProfileSchema.as_form),
    s3_client: S3StorageClient = Depends(get_s3_storage_client),
    authorization: str | None = Header(None),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
):
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    bearer = authorization.split()

    if len(bearer) != 2 or bearer[0] != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    try:
        token = jwt_manager.decode_access_token(bearer[1])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user = token["user_id"]
    role = token.get("is_admin", False)

    if user != user_id and not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    search_user = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(search_user)
    db_user = result.scalar_one_or_none()

    if db_user is None or not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result_profile = await db.execute(profile)
    user_profile = result_profile.scalar_one_or_none()

    if user_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    file_key = f"{user_id}_avatar.jpg"
    try:
        avatar = await user_data.avatar.read()
        await s3_client.upload_file(
            file_name=file_key,
            file_data=avatar,
        )
        avatar_url = await s3_client.get_file_url(file_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    user_profile_model = UserProfileModel(
        user_id=user_id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        gender=user_data.gender,
        date_of_birth=user_data.date_of_birth,
        info=user_data.info,
        avatar=avatar_url,
    )

    db.add(user_profile_model)
    await db.commit()
    await db.refresh(user_profile_model)

    return user_profile_model
