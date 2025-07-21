from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from schemas.accounts import (
    UserRegistrationSchema,
    UserResponseSchema,
    AccountActivationSchema,
    PasswordResetRequestSchema,
    PasswordResetSchema,
    TokenResponseSchema,
    LoginSchema
)
from models import User, ActivationToken, PasswordResetToken
from dependencies import get_accounts_email_notificator, get_settings
from infrastructure.email import EmailSenderInterface
from config.settings import BaseAppSettings
from datetime import datetime, timedelta
import uuid
from auth import (
    create_access_token,
    get_password_hash,
    verify_password,
    get_current_user
)

router = APIRouter()


@router.post("/register/", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
async def register_user(
        data: UserRegistrationSchema,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
        settings: BaseAppSettings = Depends(get_settings)
):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    # Create new user
    new_user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_active=False  # User needs to activate account
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create activation token
    activation_token = ActivationToken(
        token=str(uuid.uuid4()),
        user_id=new_user.id,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.add(activation_token)
    db.commit()

    # Send activation email
    activation_link = f"{settings.frontend_base_url}/accounts/activate/{activation_token.token}"

    background_tasks.add_task(
        email_sender.send_account_activation_email,
        str(data.email),
        activation_link
    )

    return new_user


@router.post("/login/", response_model=TokenResponseSchema)
async def login_user(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not activated. Please check your email."
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/activate/")
async def activate_account(
        data: AccountActivationSchema,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
        settings: BaseAppSettings = Depends(get_settings)
):
    activation_token = db.query(ActivationToken).filter(
        ActivationToken.token == data.token,
        ActivationToken.expires_at > datetime.utcnow()
    ).first()

    if not activation_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user = db.query(User).get(activation_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account already activated."
        )

    # Activate user account
    user.is_active = True
    db.commit()

    # Delete activation token
    db.delete(activation_token)
    db.commit()

    # Send confirmation email
    login_link = f"{settings.frontend_base_url}/accounts/login/"

    background_tasks.add_task(
        email_sender.send_account_activated_email,
        str(user.email),
        login_link
    )

    return {"message": "Account activated successfully"}


@router.post("/password-reset-request/")
async def request_password_reset_token(
        data: PasswordResetRequestSchema,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
        settings: BaseAppSettings = Depends(get_settings)
):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # For security, don't reveal if email exists or not
        return {"message": "If your email is registered, you'll receive a password reset link."}

    # Delete any existing reset tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id
    ).delete()

    # Create new reset token
    reset_token = PasswordResetToken(
        token=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )
    db.add(reset_token)
    db.commit()

    # Send password reset email
    reset_link = f"{settings.frontend_base_url}/accounts/reset-password/{reset_token.token}"

    background_tasks.add_task(
        email_sender.send_password_reset_request_email,
        str(data.email),
        reset_link
    )

    return {"message": "Password reset email sent"}


@router.post("/reset-password/")
async def reset_password(
        data: PasswordResetSchema,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
        settings: BaseAppSettings = Depends(get_settings)
):
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == data.token,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token."
        )

    user = db.query(User).get(reset_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Update password
    user.hashed_password = get_password_hash(data.new_password)
    db.commit()

    # Delete reset token
    db.delete(reset_token)
    db.commit()

    # Send confirmation email
    login_link = f"{settings.frontend_base_url}/accounts/login/"

    background_tasks.add_task(
        email_sender.send_password_reset_complete_email,
        str(user.email),
        login_link
    )

    return {"message": "Password reset successful"}


@router.get("/me/", response_model=UserResponseSchema)
async def get_current_user_profile(
        current_user: User = Depends(get_current_user)
):
    return current_user
