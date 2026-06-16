from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import (get_db,
                      UserModel, UserGroupEnum, UserProfileModel)
from security.interfaces import JWTAuthManagerInterface
from schemas.profiles import ProfileCreationSchema, ProfileResponseSchema
from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import TokenExpiredError, InvalidTokenError
from storages import S3StorageInterface
from sqlalchemy.orm import joinedload
router = APIRouter()

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
        request: Request,
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> int:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )

    try:
        scheme, token = auth_header.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    try:
        payload = jwt_manager.decode_access_token(token)

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        return user_id

    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=201)
async def create_profile(
        user_id: int,
        user_info: ProfileCreationSchema = Depends(),
        current_user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == current_user_id)
    )
    result = await db.execute(stmt)
    current_user = result.scalar_one_or_none()

    if current_user_id != user_id:

        if current_user.group.name != UserGroupEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )
    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or user.is_active is False:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found or not active.")
    profile = user.profile
    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )
    avatar_bytes = await user_info.avatar.read()
    file_name = f"avatars/{user_id}_avatar.jpg"
    try:
        await s3_client.upload_file(file_name, avatar_bytes)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )
    avatar_url = await s3_client.get_file_url(file_name)

    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=user_info.first_name,
            last_name=user_info.last_name,
            avatar=file_name,
            gender=user_info.gender, # noqa
            date_of_birth=user_info.date_of_birth,
            info=user_info.info
        )
        db.add(new_profile)
        await db.flush()
        await db.commit()
        await db.refresh(new_profile)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation."
        ) from e
    else:
        new_profile.avatar = avatar_url
        return ProfileResponseSchema.model_validate(new_profile)
