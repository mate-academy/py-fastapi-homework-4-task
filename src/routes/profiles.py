from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.session_postgresql import get_db
from src.database.models.accounts import UserModel, UserGroupEnum
from src.database.models.profiles import UserProfileModel
from src.schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from src.security.http import get_current_user

router = APIRouter()

@router.post("/profiles", response_model=ProfileResponseSchema)
def create_profile(
    profile_data: ProfileRequestSchema,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    data_user_id = profile_data.user_id
    user = db.query(UserModel).filter(UserModel.id == data_user_id).first()

    # Перевірка чи існує користувач
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Перевірка чи користувач активний
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive."
        )

    # Перевірка прав доступу
    if not data_user_id or (user_id != data_user_id and user.group.name != UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    # Перевірка чи профіль вже існує
    profile = db.query(UserProfileModel).filter(UserProfileModel.user_id == data_user_id).first()
    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile. Please update your existing profile instead."
        )

    try:
        new_profile = UserProfileModel(
            user_id=data_user_id,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            gender=profile_data.gender
        )
        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)
        return new_profile
    except SQLAlchemyError as e:
        print(f"Database error: {e}")  # Логування помилки
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user profile creation."
        )
