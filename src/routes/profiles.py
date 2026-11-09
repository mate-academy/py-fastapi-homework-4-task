from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileCreateResponseSchema, ProfileCreateRequestSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileCreateResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_user_profile(
        user_id: int,
        token: Annotated[str, Depends(get_token)],
        db_session: Annotated[AsyncSession, Depends(get_db)],
        jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
        s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
        profile_data: Annotated[ProfileCreateRequestSchema, Depends(ProfileCreateRequestSchema.as_form)],
):
    try:
        token_dict = jwt_manager.decode_access_token(token)
    except BaseSecurityError:
        raise HTTPException(status_code=401, detail="Token has expired.")

    stmt_1 = (
        select(UserModel)
        .options(
            joinedload(UserModel.group)
        )
        .where(UserModel.id == token_dict["user_id"])
    )
    user_from_token = await db_session.scalar(stmt_1)
    if user_from_token.id != user_id and user_from_token.group.name not in [UserGroupEnum.MODERATOR,
                                                                            UserGroupEnum.ADMIN]:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    stmt_2 = (
        select(UserModel)
        .options(
            joinedload(UserModel.profile)
        )
        .where(UserModel.id == user_id)
    )
    user_from_path = await db_session.scalar(stmt_2)
    if user_from_path is None or not user_from_path.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if user_from_path.profile is not None:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    try:
        await profile_data.avatar.seek(0)
        avatar = await profile_data.avatar.read()
        ext = profile_data.avatar.filename.split(".")[-1].lower()
        file_name = f"avatars/{user_id}_avatar.{ext}"
        await s3_client.upload_file(file_name=file_name, file_data=avatar)

        file_url = await s3_client.get_file_url(file_name=file_name)
    except BaseS3Error:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")
    profile = UserProfileModel(
        **profile_data.model_dump(exclude={"avatar"}),
        user_id=user_id,
        avatar=file_name
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    profile.avatar = file_url
    return profile
