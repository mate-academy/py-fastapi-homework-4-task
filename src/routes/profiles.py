from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import TokenExpiredError, S3FileUploadError, S3ConnectionError, InvalidTokenError
from schemas import ProfileResponseSchema, ProfileCreateRequestSchema
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
        user_id: int,
        user_data: ProfileCreateRequestSchema = Depends(
            ProfileCreateRequestSchema.from_form
        ),
        session: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        val_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token."
        )
    req_user_id = val_token.get("user_id")
    result = await session.execute(
        select(UserModel)
        .filter_by(id=user_id)
        .options(
            joinedload(UserModel.profile),
            joinedload(UserModel.group)
        )
    )
    user = result.scalars().first()
    result = await session.execute(
        select(UserModel)
        .filter_by(id=req_user_id)
        .options(
            joinedload(UserModel.group)
        )
    )
    req_user = result.scalars().first()
    if (
            not user
            or not req_user
            or not user.is_active
    ):
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )
    if user_id != req_user_id and req_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile."
        )
    if user.profile:
        raise HTTPException(
            status_code=400,
            detail="User already has a profile."
        )
    avatar = user_data.avatar
    data = user_data.model_dump(exclude={"avatar"})
    file_name = f"avatars/{user.id}_{avatar.filename}"
    try:
        await s3_client.upload_file(
            file_name,
            await avatar.read()
        )
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )
    profile = UserProfileModel(
        **data,
        avatar=file_name,
        user_id=user.id
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return ProfileResponseSchema(
        id=profile.id, user_id=profile.user_id,
        first_name=profile.first_name, last_name=profile.last_name,
        gender=profile.gender, date_of_birth=profile.date_of_birth,
        info=profile.info, avatar=await s3_client.get_file_url(file_name),
    )
