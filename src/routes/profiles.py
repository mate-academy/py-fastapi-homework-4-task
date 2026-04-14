from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone

from config import get_s3_storage_client, get_jwt_auth_manager
from exceptions import InvalidTokenError, TokenExpiredError
from schemas import ProfileResponseSchema, ProfileRequestSchema
from security.http import get_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def user_profile(
        user_id: int,
        profile: ProfileRequestSchema = Depends(),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    try:
        token_data = jwt_manager.decode_access_token(token)
    except (TokenExpiredError, InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    request_user, token_user = [
        (
            await db.execute(
                select(UserModel)
                .where(UserModel.id == user_id_)
                .options(
                    joinedload(UserModel.group),
                    joinedload(UserModel.profile)
                )
            )
        ).scalar_one_or_none()
        for user_id_ in (user_id, token_data["user_id"])
    ]

    if not request_user or request_user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if request_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    if request_user.id != token_user.id and token_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )
    try:
        avatar_bytes = await profile.avatar.read()
        avatar_filename = f"avatars/{user_id}_{profile.avatar.filename}"

        await s3_client.upload_file(file_name=avatar_filename, file_data=avatar_bytes)
        profile_data = profile.__dict__
        del profile_data["avatar"]
        profile_data["avatar"] = avatar_filename
        profile_data["user_id"] = user_id

        db_res = await db.execute(
            insert(UserProfileModel)
            .values(**profile_data)
            .returning(UserProfileModel)
        )
        profile_model = db_res.scalar_one()
        await db.commit()

        profile_model.avatar = await s3_client.get_file_url(file_name=avatar_filename)
        return profile_model
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
