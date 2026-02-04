from datetime import date

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from fastapi import Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from exceptions import TokenExpiredError, InvalidTokenError
from config import get_jwt_auth_manager, get_s3_storage_client
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from database import get_db, UserModel, UserGroupEnum, UserProfileModel
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter()


async def check_auth_and_get_user(
    request: Request,
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    authorization = request.headers.get("Authorization")
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    scheme, _, token = authorization.partition(" ")
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header is missing")
    if not scheme.lower() == "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'")

    try:
        decoded_token = jwt_manager.decode_access_token(token)
        current_user_id = decoded_token.get("user_id")
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    return current_user_id


@router.post(
    "/users/{user_id}/profile/",
    summary="User Profile Creation",
    response_model=ProfileResponseSchema, status_code=201
)
async def create_user_profile(
        user_id: int,
        request: Request,
        first_name: str | None = Form(None),
        last_name: str | None = Form(None),
        gender: str | None = Form(None),
        date_of_birth: date | None = Form(None),
        info: str | None = Form(None),
        avatar: UploadFile | None = File(None),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    try:
        current_user_id = await check_auth_and_get_user(request, jwt_manager)
    except HTTPException as e:
        raise e

    data = {"first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "date_of_birth": date_of_birth,
            "info": info,
            "avatar": avatar}

    try:
        user_data = ProfileRequestSchema(**data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.json())

    avatar_key = None
    avatar_url = None

    if avatar:
        try:
            contents = await avatar.read()
            extension = avatar.filename.rsplit(".", 1)[-1]
            avatar_key = f"avatars/{user_id}_avatar.{extension}"
            await s3_client.upload_file(avatar_key, contents)
            avatar_url = await s3_client.get_file_url(avatar_key)

        except Exception:
            raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    db_data = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == current_user_id))
    current_user = db_data.scalar_one_or_none()

    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if user_id != current_user_id:
        if current_user.group.name != UserGroupEnum.ADMIN:
            raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    db_data = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group))
        .where(UserModel.id == user_id))
    profile_user = db_data.scalar_one_or_none()

    if not profile_user:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    db_data = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    existing_profile = db_data.scalar_one_or_none()
    if existing_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    profile = UserProfileModel(
        user_id=user_id,
        first_name=user_data.first_name.lower(),
        last_name=user_data.last_name.lower(),
        avatar=avatar_key,
        gender=user_data.gender,
        date_of_birth=user_data.date_of_birth,
        info=user_data.info
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    data_to_return = ProfileResponseSchema(
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url
    )

    return data_to_return
