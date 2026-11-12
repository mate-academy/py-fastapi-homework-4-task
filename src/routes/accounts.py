from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_jwt_auth_manager, get_accounts_email_notificator
from database import (
    get_db,
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel
)
from exceptions import BaseSecurityError, TokenExpiredError
from notifications import EmailSenderInterface
from schemas import (
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
    MessageResponseSchema,
    UserActivationRequestSchema,
    PasswordResetRequestSchema,
    PasswordResetCompleteRequestSchema,
    UserLoginResponseSchema,
    UserLoginRequestSchema,
    TokenRefreshRequestSchema,
    TokenRefreshResponseSchema
)
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()

ACCOUNTS_URL = "http://127.0.0.1/accounts"
LOGIN_LINK = f"{ACCOUNTS_URL}/login/"


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "description": "Conflict - User with this email already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A user with this email test@example.com already exists."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred during user creation.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred during user creation."
                    }
                }
            },
        },
    },
)
async def register_user(
    user_data: UserRegistrationRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> UserRegistrationResponseSchema:
    """
    Endpoint for user registration.
    """
    stmt = select(UserModel).where(UserModel.email == user_data.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists."
        )

    try:
        group_stmt = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
        user_group = (await db.execute(group_stmt)).scalar_one_or_none()
        if not user_group:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default user group not found."
            )

        new_user = UserModel(
            email=user_data.email,
            password=user_data.password,
            is_active=False,
            group_id=user_group.id
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationTokenModel(user_id=new_user.id)
        db.add(activation_token)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation."
        ) from e
    else:
        activation_link = f"{ACCOUNTS_URL}/activate/?token={activation_token.token}"
        background_tasks.add_task(email_sender.send_activation_email, new_user.email, activation_link)
        return UserRegistrationResponseSchema.model_validate(new_user)


@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def activate_account(
    activation_data: UserActivationRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Endpoint to activate a user's account.
    """
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .where(ActivationTokenModel.token == activation_data.token)
    )
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()

    if not token_record or not token_record.user or token_record.user.email != activation_data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        await db.delete(token_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user.is_active = True
    db.add(user)
    await db.delete(token_record)
    await db.commit()
    background_tasks.add_task(email_sender.send_activation_complete_email, user.email, LOGIN_LINK)
    return MessageResponseSchema(message="User account activated successfully.")


@router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def login_user(
    credentials: UserLoginRequestSchema,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserLoginResponseSchema:
    """
    Endpoint for user authentication and token generation.
    """
    stmt = select(UserModel).where(UserModel.email == credentials.email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not user.verify_password(credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated."
        )

    access_token = jwt_manager.create_access_token({"user_id": user.id})
    refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    try:
        await db.execute(delete(RefreshTokenModel).where(RefreshTokenModel.user_id == user.id))
        db.add(RefreshTokenModel(user_id=user.id, token=refresh_token))
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        print("LOGIN COMMIT ERROR:", repr(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request."
        )

    return UserLoginResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post(
    "/refresh/",
    response_model=TokenRefreshResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def refresh_token(
    data: TokenRefreshRequestSchema,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> TokenRefreshResponseSchema:
    """
    Endpoint to refresh access token.
    """
    try:
        payload = jwt_manager.decode_refresh_token(data.refresh_token)
        user_id = payload.get("user_id")
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token has expired."
        )
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    stmt = select(RefreshTokenModel).where(
        RefreshTokenModel.token == data.refresh_token,
        RefreshTokenModel.user_id == user_id
    )
    token_record = (await db.execute(stmt)).scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found."
        )

    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    new_access_token = jwt_manager.create_access_token({"user_id": user_id})
    return TokenRefreshResponseSchema(access_token=new_access_token, token_type="bearer")


@router.post(
    "/password-reset/request/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def request_password_reset_token(
    data: PasswordResetRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Endpoint to request a password reset token.
    """
    stmt = select(UserModel).where(UserModel.email == data.email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user and user.is_active:
        existing_token_stmt = select(PasswordResetTokenModel).where(PasswordResetTokenModel.user_id == user.id)
        existing_token = (await db.execute(existing_token_stmt)).scalar_one_or_none()
        if existing_token:
            await db.delete(existing_token)

        reset_token = PasswordResetTokenModel(user_id=user.id)
        db.add(reset_token)
        await db.commit()
        reset_link = f"{ACCOUNTS_URL}/reset-password/complete/?token={reset_token.token}"
        background_tasks.add_task(email_sender.send_password_reset_email, user.email, reset_link)

    return MessageResponseSchema(
        message="If you are registered, you will receive an email with instructions."
    )


@router.post(
    "/reset-password/complete/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def reset_password(
    data: PasswordResetCompleteRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Endpoint for resetting a user's password.
    """
    user = (await db.execute(
        select(UserModel).where(UserModel.email == data.email)
    )).scalar_one_or_none()

    token_record = None
    if user:
        token_record = (await db.execute(
            select(PasswordResetTokenModel).where(PasswordResetTokenModel.user_id == user.id)
        )).scalar_one_or_none()

    invalid = not user or not token_record or token_record.token != data.token
    if not invalid:
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        invalid = expires_at < datetime.now(timezone.utc)

    if invalid:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token."
        )

    try:
        user.password = data.password
        db.add(user)
        await db.delete(token_record)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password."
        ) from e

    background_tasks.add_task(email_sender.send_password_reset_complete_email, str(data.email), LOGIN_LINK)
    return MessageResponseSchema(message="Password reset successfully.")
