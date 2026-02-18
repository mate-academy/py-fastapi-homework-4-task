from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy import select
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.dependencies import get_db, get_current_user, get_s3_storage_client
from src.database.models import UserModel, ProfileModel
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from validation import validate_image
from storages import S3StorageInterface

router = APIRouter()

@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    user_id: int,
    background_tasks: BackgroundTasks,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    # --- Authorization check ---
    # get_current_user вже робить валідацію токена і викидає HTTPException 401 при проблемах
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    # --- Check user existence and status ---
    user = await db.get(UserModel, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    # --- Check existing profile ---
    existing_profile_result = await db.execute(select(ProfileModel).where(ProfileModel.user_id == user_id))
    if existing_profile_result.scalars().first():
        raise HTTPException(status_code=400, detail="User already has a profile.")

    # --- Validate input data (without avatar) ---
    try:
        profile_data = ProfileRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date.fromisoformat(date_of_birth),
            info=info,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # --- Validate avatar image ---
    contents = await avatar.read()
    if not validate_image(contents, avatar.filename):
        raise HTTPException(status_code=400, detail="Invalid avatar image format or size.")
    await avatar.seek(0)  # Reset file pointer if needed later

    # --- Upload avatar to S3 ---
    try:
        avatar_url = await s3_client.upload_avatar(user_id, avatar.filename, contents)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    # --- Create profile record ---
    profile = ProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema.from_orm(profile)
