from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db, UserProfileModel
from database.models.accounts import GenderEnum
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from validation import validate_image
from security.http import get_token
from config.dependencies import get_jwt_auth_manager, get_s3_storage_client

router = APIRouter()

@router.post("/",
             response_model=ProfileResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Create User profile",
             description="Створює профіль користувача, завантажує аватар у MinIO та зберігає метадані в БД."
)
async def create_profile(
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
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in token",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    validate_image(avatar)

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists for this user.",
        )

    object_key = f"avatars/{user_id}_{avatar.filename}"

    try:
        avatar_url = await s3_client.upload_file(avatar, object_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image to storage: {str(e)}"
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
