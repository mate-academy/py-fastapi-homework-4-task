from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from exceptions import S3FileUploadError, TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileResponseSchema, ProfileSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from fastapi import Header

router = APIRouter()


async def get_current_user(
        user_id: int,
        authorization: str | None = Header(default=None),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    if not authorization:
        raise HTTPException(401, "Authorization header is missing")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Invalid Authorization header format. Expected 'Bearer <token>'")

    try:
        jwt_manager.verify_access_token_or_raise(token)
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(401, "Token has expired.")
    except InvalidTokenError:
        raise HTTPException(401, "Invalid Authorization header format. Expected 'Bearer <token>'")

    user = (await db.execute(
        select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == payload["user_id"])
    )).scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(401, "User not found or not active.")
    return user


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=201)
async def create_user_profile(
        user_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        profile_data: ProfileSchema = Depends(ProfileSchema.from_form),
):
    if not current_user.has_group(UserGroupEnum.ADMIN) and current_user.id != user_id:
        raise HTTPException(403, "You don't have permission to edit this profile.")

    existing = (await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)   # user_id, а не current_user_id
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(400, "User already has a profile.")

    avatar_bytes = await profile_data.avatar.read()
    extension = (profile_data.avatar.filename or "avatar.jpg").rsplit(".", 1)[-1].lower()
    avatar_key = f"avatars/{user_id}_avatar.{extension}"

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
        avatar_url = await s3_client.get_file_url(avatar_key)
    except S3FileUploadError as error:
        print(f"Error uploading avatar to S3: {error}")
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    try:
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating the profile.",
        )

    avatar_url = await s3_client.get_file_url(new_profile.avatar)

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
