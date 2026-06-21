from datetime import date

from fastapi import (
    APIRouter,
    UploadFile,
    Form,
    File,
    HTTPException,
    Path,
    Header,
    status,
    Depends
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import UserModel, get_db, UserGroupEnum, UserProfileModel
from database.models.accounts import GenderEnum
from exceptions import TokenExpiredError, InvalidTokenError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    user_id: int = Path(...),
    authorization: str | None = Header(None),

    first_name: str | None = Form(None),
    last_name: str | None = Form(None),
    gender: str | None = Form(None),
    date_of_birth: date | None = Form(None),
    info: str | None = Form(None),
    avatar: UploadFile | None = File(None),

    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
):
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization.removeprefix("Bearer ")

    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload["user_id"]
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token."
        )

    stmt = (
        select(UserModel)
        .where(UserModel.id == token_user_id)
        .options(joinedload(UserModel.group))
    )
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    if (
        current_user.group_id != 3
        and token_user_id != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    stmt = select(UserModel).where(
        UserModel.id == user_id
    )
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    stmt = select(UserProfileModel).where(
        UserProfileModel.user_id == user_id
    )
    result = await db.execute(stmt)
    existing_profile = result.scalars().first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        profile = ProfileRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    try:
        file_name = f"avatars/{user_id}_avatar.jpg"

        file_data = await avatar.read()

        await s3_client.upload_file(
            file_name=file_name,
            file_data=file_data
        )

        avatar_url = await s3_client.get_file_url(
            file_name
        )

    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    profile_model = UserProfileModel(
        first_name=profile.first_name.lower(),
        last_name=profile.last_name.lower(),
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=file_name,
        user_id=user_id,
    )

    try:
        db.add(profile_model)
        await db.commit()
        await db.refresh(profile_model)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error."
        ) from e

    return ProfileResponseSchema(
        id=profile_model.id,
        first_name=profile_model.first_name,
        last_name=profile_model.last_name,
        gender=profile_model.gender,
        date_of_birth=profile_model.date_of_birth,
        info=profile_model.info,
        avatar=avatar_url,
    )
