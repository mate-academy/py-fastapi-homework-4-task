from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from src.database import get_db
from src.database import UserModel, UserProfileModel, UserGroupEnum
from src.exceptions import TokenExpiredError, BaseS3Error
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface
from src.storages.interfaces import S3StorageInterface
from src.validation import validate_image
from src.schemas.profiles import UserProfileCreateSchema, UserProfileResponseSchema

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserProfileResponseSchema,
)
async def create_user_profile(
    user_id: int,
    request: Request,
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),

    first_name: str | None = Form(None),
    last_name: str | None = Form(None),
    gender: str | None = Form(None),
    date_of_birth: date | None = Form(None),
    info: str | None = Form(None),
    avatar: UploadFile | None = File(None),
):
    token = get_token(request)

    try:
        decoded = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")

    token_user_id: int = decoded["user_id"]

    if avatar is None:
        raise RequestValidationError([{
            "loc": ("body", "avatar"),
            "msg": "Field required",
            "type": "missing"
        }])

    try:
        payload = UserProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
        )
        validate_image(avatar)
    except ValidationError as e:
        raise RequestValidationError(e.errors())
    except ValueError as e:
        raise RequestValidationError([{
            "loc": ("body", "avatar"),
            "msg": str(e),
            "type": "value_error"
        }])

    auth_user = await db.scalar(
        select(UserModel)
        .options(joinedload(UserModel.group), joinedload(UserModel.profile))
        .where(UserModel.id == token_user_id)
    )

    if not auth_user or auth_user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    # 5) Permission: звичайний USER не може створювати профіль іншому
    if token_user_id != user_id and auth_user.group.name == UserGroupEnum.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    # 6) Target user (для admin)
    target_user = auth_user
    if user_id != token_user_id:
        target_user = await db.scalar(
            select(UserModel)
            .options(joinedload(UserModel.profile))
            .where(UserModel.id == user_id)
        )
        if not target_user or target_user.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )

    if target_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # 7) S3 upload (ключ як у тесті)
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    content = await avatar.read()
    await avatar.seek(0)

    try:
        await s3.upload_file(avatar_key, content)
    except BaseS3Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    profile = UserProfileModel(
        user_id=target_user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        info=payload.info,
        avatar=avatar_key,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3.get_file_url(avatar_key)

    return UserProfileResponseSchema(
        id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=avatar_url,
    )
