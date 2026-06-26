from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from config import get_s3_storage_client, get_jwt_auth_manager
from exceptions import InvalidTokenError, BaseS3Error, TokenExpiredError
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201,
)
async def user_profile(
    user_id: int,
    data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    try:
        verify_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    user = await db.scalar(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == int(verify_token["user_id"]))
    )
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401, detail="User not found or not active."
        )
    if user.id != user_id and not user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile.",
        )

    profile = await db.scalar(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if profile:
        raise HTTPException(
            status_code=400, detail="User already has a profile."
        )

    try:
        file_name = f"avatars/{user_id}_avatar.jpg"
        file_bytes = await data.avatar.read()
        await s3_client.upload_file(file_name=file_name, file_data=file_bytes)
        file_url = await s3_client.get_file_url(file_name=file_name)
    except BaseS3Error:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later.",
        )

    try:

        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=data.first_name,
            last_name=data.last_name,
            gender=data.gender,
            date_of_birth=data.date_of_birth,
            info=data.info,
            avatar=file_name,
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation.",
        ) from e

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=file_url,
    )
