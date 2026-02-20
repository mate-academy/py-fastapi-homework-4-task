from fastapi import APIRouter, HTTPException, Header
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_s3_storage_client, get_jwt_auth_manager
from exceptions import TokenExpiredError
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from database import get_db, UserModel, UserProfileModel
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def get_current_user_payload(
    auth_header: str | None = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> dict:

    if not auth_header:
        raise HTTPException(401, "Authorization header is missing")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            401,
            "Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")

    return payload


@router.post(
    "/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=201
)
async def user_profile_create(
    user_id: int,
    payload: dict = Depends(get_current_user_payload),
    profile: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):

    user = await db.get(UserModel, user_id)
    current_user = await db.get(UserModel, payload.get("user_id"))
    is_admin = current_user.group_id == 3

    if payload.get("user_id") != user_id and not is_admin:
        raise HTTPException(
            status_code=403, detail="You don't have permission to edit this profile."
        )

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    existing_user = await db.scalar(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    avatar_bytes = await profile.avatar.read()
    file_name = f"avatars/{user_id}_avatar.jpg"
    try:
        await s3_client.upload_file(
            file_name=file_name,
            file_data=avatar_bytes,
        )
    except Exception:
        raise HTTPException(
            status_code=500, detail="Failed to upload avatar. Please try again later."
        )

    created_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=file_name,
    )

    db.add(created_profile)
    await db.commit()
    await db.refresh(created_profile)

    avatar_url = await s3_client.get_file_url(file_name=file_name)

    return ProfileResponseSchema(
        id=created_profile.id,
        user_id=created_profile.user_id,
        first_name=created_profile.first_name,
        last_name=created_profile.last_name,
        gender=created_profile.gender,
        date_of_birth=str(created_profile.date_of_birth),
        info=created_profile.info,
        avatar=avatar_url,
    )
