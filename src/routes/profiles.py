from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import BaseS3Error, BaseSecurityError
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema

from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from database.models.accounts import GenderEnum
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int,
    data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
    session: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    token_user_id = decoded_token["user_id"]

    requester = await session.scalar(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == token_user_id)
    )
    is_admin = requester is not None and requester.group.name == UserGroupEnum.ADMIN

    if token_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    user_result = await session.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    user_profile = (
        await session.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        )
    ).scalar_one_or_none()

    if user_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_key = f"avatars/{user.id}_avatar.jpg"
    contents = await data.avatar.read()

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=contents)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    avatar_url = await s3_client.get_file_url(avatar_key)

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=GenderEnum(data.gender),
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=avatar_key,
    )

    session.add(new_profile)
    await session.commit()
    await session.refresh(new_profile)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url,
    )
