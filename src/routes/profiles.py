from datetime import date

from fastapi import APIRouter, status, Depends, HTTPException, UploadFile, \
    Form, File
from poetry.console.commands import self
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, UserModel, UserProfileModel
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image

router = APIRouter()

@router.post(path="/users/{user_id}/profile/",
             response_model=ProfileResponseSchema,
             status_code=status.HTTP_201_CREATED)
async def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    token: str = Depends(get_token),
    jwt_auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    try:
        payload = jwt_auth_manager.decode_token(token)
    except Exception as e:
        err_msg = str(e).lower()
        if "expired" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )
    requester_id_str = payload.get("sub") or payload.get("user_id")
    if not requester_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )
    requester_id = int(requester_id_str)

    requester_stmt = (select(UserModel)
                      .options(selectinload(UserModel.group))
                      .where(UserModel.id == requester_id))

    requester_result = await db.execute(requester_stmt)
    current_user = requester_result.scalar_one_or_none()
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )
    is_admin = False
    if current_user.group:
        group_name = getattr(current_user.group.name, "name",
                             str(current_user.group.name))
        is_admin = group_name.upper() == "ADMIN"

    if requester_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    target_user_stmt = (
        select(UserModel)
        .options(selectinload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    target_user_result = await db.execute(target_user_stmt)
    target_user = target_user_result.scalar_one_or_none()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if target_user.profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
            profile_data = ProfileRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    try:
        validate_image(avatar)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    file_ext = avatar.filename.split(".")[-1] if avatar.filename else "jpg"
    s3_file_path = f"avatars/{user_id}_avatar.{file_ext}"
    try:
        file_bytes = await avatar.read()
        avatar_url = await s3_client.upload_file(file_data=file_bytes,
                                                 file_name=s3_file_path)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url,
    )
    db.add(new_profile)
    try:
        await db.commit()
        await db.refresh(new_profile)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save profile to database.",
        )

    return new_profile