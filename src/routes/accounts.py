import os
from datetime import datetime, timezone
from typing import cast
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import (
    BaseAppSettings,
    get_accounts_email_notificator,
    get_jwt_auth_manager,
    get_settings,
)
from database import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserGroupEnum,
    UserGroupModel,
    UserModel,
    get_db,
)
from exceptions import BaseSecurityError
from notifications import EmailSenderInterface
from schemas import (
    MessageResponseSchema,
    PasswordResetCompleteRequestSchema,
    PasswordResetRequestSchema,
    TokenRefreshRequestSchema,
    TokenRefreshResponseSchema,
    UserActivationRequestSchema,
    UserLoginRequestSchema,
    UserLoginResponseSchema,
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
)
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")


def build_account_link(
    path: str,
    email: str | None = None,
    token: str | None = None,
) -> str:
    url = f"{PUBLIC_BASE_URL}/api/v1/accounts/{path.lstrip('/')}"

    params = {}

    if email is not None:
        params["email"] = email

    if token is not None:
        params["token"] = token

    if params:
        url = f"{url}?{urlencode(params)}"

    return url


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
)
async def register_user(
    user_data: UserRegistrationRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(
        get_accounts_email_notificator
    ),
) -> UserRegistrationResponseSchema:
    result = await db.execute(
        select(UserModel).where(
            UserModel.email == user_data.email
        )
    )
    existing_user = result.scalars().first()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A user with this email "
                f"{user_data.email} already exists."
            ),
        )

    result = await db.execute(
        select(UserGroupModel).where(
            UserGroupModel.name == UserGroupEnum.USER
        )
    )
    user_group = result.scalars().first()

    if user_group is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default user group not found.",
        )

    try:
        new_user = UserModel.create(
            email=str(user_data.email),
            raw_password=user_data.password,
            group_id=user_group.id,
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationTokenModel(
            user_id=new_user.id
        )
        db.add(activation_token)
        await db.flush()

        recipient_email = str(new_user.email)
        token_value = str(activation_token.token)

        await db.commit()
        await db.refresh(new_user)

    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation.",
        ) from error

    activation_link = build_account_link(
        "activate/",
        email=recipient_email,
        token=token_value,
    )

    background_tasks.add_task(
        email_sender.send_activation_email,
        recipient_email,
        activation_link,
    )

    return UserRegistrationResponseSchema.model_validate(
        new_user
    )


@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Activate User Account",
)
async def activate_account(
    activation_data: UserActivationRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(
        get_accounts_email_notificator
    ),
) -> MessageResponseSchema:
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .join(UserModel)
        .where(
            UserModel.email == activation_data.email,
            ActivationTokenModel.token == activation_data.token,
        )
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)

    if (
        token_record is None
        or cast(datetime, token_record.expires_at).replace(
            tzinfo=timezone.utc
        ) < now_utc
    ):
        if token_record is not None:
            await db.delete(token_record)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token.",
        )

    user = token_record.user

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active.",
        )

    recipient_email = str(user.email)

    user.is_active = True
    await db.delete(token_record)
    await db.commit()

    background_tasks.add_task(
        email_sender.send_activation_complete_email,
        recipient_email,
        build_account_link("login/"),
    )

    return MessageResponseSchema(
        message="User account activated successfully."
    )


@router.post(
    "/password-reset/request/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Request Password Reset Token",
)
async def request_password_reset_token(
    data: PasswordResetRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(
        get_accounts_email_notificator
    ),
) -> MessageResponseSchema:
    response_message = (
        "If you are registered, you will receive "
        "an email with instructions."
    )

    result = await db.execute(
        select(UserModel).filter_by(email=data.email)
    )
    user = result.scalars().first()

    if user is None or not user.is_active:
        return MessageResponseSchema(
            message=response_message
        )

    await db.execute(
        delete(PasswordResetTokenModel).where(
            PasswordResetTokenModel.user_id == user.id
        )
    )

    reset_token = PasswordResetTokenModel(
        user_id=cast(int, user.id)
    )
    db.add(reset_token)
    await db.flush()

    recipient_email = str(user.email)
    token_value = str(reset_token.token)

    await db.commit()

    reset_link = build_account_link(
        "reset-password/complete/",
        email=recipient_email,
        token=token_value,
    )

    background_tasks.add_task(
        email_sender.send_password_reset_email,
        recipient_email,
        reset_link,
    )

    return MessageResponseSchema(
        message=response_message
    )


@router.post(
    "/reset-password/complete/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Reset User Password",
)
async def reset_password(
    data: PasswordResetCompleteRequestSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(
        get_accounts_email_notificator
    ),
) -> MessageResponseSchema:
    result = await db.execute(
        select(UserModel).filter_by(email=data.email)
    )
    user = result.scalars().first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token.",
        )

    result = await db.execute(
        select(PasswordResetTokenModel).filter_by(
            user_id=user.id
        )
    )
    token_record = result.scalars().first()

    if (
        token_record is None
        or token_record.token != data.token
    ):
        if token_record is not None:
            await db.delete(token_record)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token.",
        )

    expires_at = cast(
        datetime,
        token_record.expires_at,
    ).replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        await db.delete(token_record)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token.",
        )

    recipient_email = str(user.email)

    try:
        user.password = data.password
        await db.delete(token_record)
        await db.commit()

    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password.",
        ) from error

    background_tasks.add_task(
        email_sender.send_password_reset_complete_email,
        recipient_email,
        build_account_link("login/"),
    )

    return MessageResponseSchema(
        message="Password reset successfully."
    )


@router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="User Login",
)
async def login_user(
    login_data: UserLoginRequestSchema,
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
    jwt_manager: JWTAuthManagerInterface = Depends(
        get_jwt_auth_manager
    ),
) -> UserLoginResponseSchema:
    result = await db.execute(
        select(UserModel).filter_by(
            email=login_data.email
        )
    )
    user = result.scalars().first()

    if (
        user is None
        or not user.verify_password(login_data.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    jwt_refresh_token = jwt_manager.create_refresh_token(
        {"user_id": user.id}
    )

    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id,
            days_valid=settings.LOGIN_TIME_DAYS,
            token=jwt_refresh_token,
        )
        db.add(refresh_token)
        await db.flush()
        await db.commit()

    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        ) from error

    jwt_access_token = jwt_manager.create_access_token(
        {"user_id": user.id}
    )

    return UserLoginResponseSchema(
        access_token=jwt_access_token,
        refresh_token=jwt_refresh_token,
    )


@router.post(
    "/refresh/",
    response_model=TokenRefreshResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
)
async def refresh_access_token(
    token_data: TokenRefreshRequestSchema,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(
        get_jwt_auth_manager
    ),
) -> TokenRefreshResponseSchema:
    try:
        decoded_token = jwt_manager.decode_refresh_token(
            token_data.refresh_token
        )
        user_id = decoded_token.get("user_id")

    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    result = await db.execute(
        select(RefreshTokenModel).filter_by(
            token=token_data.refresh_token
        )
    )
    refresh_token_record = result.scalars().first()

    if refresh_token_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    result = await db.execute(
        select(UserModel).filter_by(id=user_id)
    )
    user = result.scalars().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    new_access_token = jwt_manager.create_access_token(
        {"user_id": user_id}
    )

    return TokenRefreshResponseSchema(
        access_token=new_access_token
    )
