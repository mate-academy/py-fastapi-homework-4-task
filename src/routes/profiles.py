from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db, UserProfileModel, UserModel, UserGroupEnum
from database.models.accounts import GenderEnum
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from security.http import get_token
from config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from exceptions import BaseSecurityError

router = APIRouter()

@router.post("/users/{user_id}/profile/",
             response_model=ProfileResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Create User profile",
)
async def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: GenderEnum = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager = Depends(get_jwt_auth_manager),
    s3_client = Depends(get_s3_storage_client)
):
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")

    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


    user_stmt = select(UserModel).where(UserModel.id == token_user_id)
    user_result = await db.execute(user_stmt)
    current_user = user_result.scalars().first()

    target_user_stmt = select(UserModel).where(UserModel.id == user_id)
    target_user_result = await db.execute(target_user_stmt)
    target_user = target_user_result.scalars().first()

    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    is_admin = current_user.group.name == UserGroupEnum.ADMIN
    if token_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    ProfileCreateSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender.value,
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar
    )
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    object_key = f"avatars/{user_id}_{avatar.filename}"

    try:
        avatar_url = await s3_client.upload_file(avatar, object_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar_url,
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        return new_profile
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving the profile to the database."
        )
