from fastapi import APIRouter, Depends, HTTPException, Header, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import TokenExpiredError, S3ConnectionError, S3FileUploadError

from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def validate_authorization(
    authorization: str | None = Header(default=None),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> dict:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
    try:
        payload = jwt_manager.decode_access_token(parts[1])
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired."
        )

    return payload


@router.post("/users/{user_id}/profile/", status_code=201, response_model=ProfileResponseSchema)
async def create_profile(
        user_id: int,
        profile_data: ProfileCreateSchema = Form(),
        payload: dict = Depends(validate_authorization),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == payload.get("user_id"))
    )
    current_user = result.scalar_one_or_none()

    if current_user is None or current_user.is_active is False:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if user_id != current_user.id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is not None:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    file_data = await profile_data.avatar.read()

    file_name = f"avatars/{user_id}_avatar.jpg"
    try:
        await s3_client.upload_file(file_name, file_data)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=file_name
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3_client.get_file_url(file_name)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )
