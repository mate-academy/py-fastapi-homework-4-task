from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from security import get_token
from database import get_db
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from models import UserModel, UserProfileModel
from storages import S3StorageInterface, get_s3_storage_client
from notifications import EmailSenderInterface, get_accounts_email_notificator

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
def create_profile(
        user_id: int,
        profile_data: ProfileCreateSchema,
        token: str = Depends(get_token),
        db: Session = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
        background_tasks: BackgroundTasks
):
    # Перевірка токена та авторизації
    user = db.query(UserModel).filter(UserModel.id == user_id, UserModel.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    if user.profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    # Завантаження аватара до MinIO
    avatar_url = None
    if profile_data.avatar:
        try:
            avatar_url = s3_client.upload_file(profile_data.avatar, f"avatars/{user_id}_avatar.jpg")
        except Exception:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to upload avatar. Please try again later.")

    # Створення профілю
    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile
