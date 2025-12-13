import shutil
import uuid
import inspect
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from database import get_db, UserProfileModel, UserModel
from schemas.profiles import ProfileCreateRequestSchema, ProfileResponseSchema, GenderEnum
from config import get_jwt_auth_manager, get_s3_storage_client
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from config.dependencies import oauth2_scheme

router = APIRouter()


def get_token_manual(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'")

    return token


def get_profile_form_data(
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: str = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...)
) -> ProfileCreateRequestSchema:
    try:
        return ProfileCreateRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(include_url=False, include_input=False, include_context=False)
        )


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
        user_id: int,
        profile_data: Annotated[ProfileCreateRequestSchema, Depends(get_profile_form_data)],
        token: str = Depends(get_token_manual),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except Exception as e:
        if "expired" in str(e).lower():
            raise HTTPException(status_code=401, detail="Token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_user_id = payload.get("user_id")
    if token_user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(UserModel).where(UserModel.id == token_user_id))
    current_user = result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    is_admin = (current_user.group_id == 3)
    if not is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    query = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(query)
    existing_profile = result.scalars().first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        file_extension = profile_data.avatar.filename.split('.')[-1]
        file_path = f"avatars/{user_id}_avatar.{file_extension}"

        upload_result = s3_client.upload_file(
            profile_data.avatar.file,
            file_path
        )

        if inspect.iscoroutine(upload_result):
            avatar_url = await upload_result
        else:
            avatar_url = upload_result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Мапінг статі для БД
    gender_db_value = profile_data.gender.upper()
    if gender_db_value not in ["MAN", "WOMAN"]:
        gender_db_value = "OTHER"

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,  # Вже lower() зі схеми
        last_name=profile_data.last_name,  # Вже lower() зі схеми
        gender=gender_db_value,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=str(avatar_url)
    )

    db.add(new_profile)

    try:
        await db.commit()
        await db.refresh(new_profile)
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

    return new_profile