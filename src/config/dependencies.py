import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.future import select

from config.settings import TestingSettings, Settings, BaseAppSettings
from notifications import EmailSenderInterface, EmailSender
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager
from storages import S3StorageInterface, S3StorageClient
from database.models.accounts import UserModel


def get_settings() -> BaseAppSettings:
    """
    Retrieve the application settings based on the current environment.
    """
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "testing":
        return TestingSettings()
    return Settings()


def get_jwt_auth_manager(settings: BaseAppSettings = Depends(get_settings)) -> JWTAuthManagerInterface:
    """
    Create and return a JWT authentication manager instance.
    """
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


def get_accounts_email_notificator(
    settings: BaseAppSettings = Depends(get_settings)
) -> EmailSenderInterface:
    """
    Retrieve an instance of the EmailSenderInterface configured with the application settings.
    """
    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        email=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        template_dir=settings.PATH_TO_EMAIL_TEMPLATES_DIR,
        activation_email_template_name=settings.ACTIVATION_EMAIL_TEMPLATE_NAME,
        activation_complete_email_template_name=settings.ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME,
        password_email_template_name=settings.PASSWORD_RESET_TEMPLATE_NAME,
        password_complete_email_template_name=settings.PASSWORD_RESET_COMPLETE_TEMPLATE_NAME
    )


def get_s3_storage_client(
    settings: BaseAppSettings = Depends(get_settings)
) -> S3StorageInterface:
    """
    Retrieve an instance of the S3StorageInterface configured with the application settings.
    """
    return S3StorageClient(
        endpoint_url=settings.S3_STORAGE_ENDPOINT,
        access_key=settings.S3_STORAGE_ACCESS_KEY,
        secret_key=settings.S3_STORAGE_SECRET_KEY,
        bucket_name=settings.S3_BUCKET_NAME
    )


# Instantiate the HTTPBearer security token extraction scheme
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    """
    Extracts the Bearer token from the Authorization header, decodes and validates
    it using the JWT authentication manager, and fetches the corresponding User record
    from the database. Supports both standard 'sub' and custom 'user_id' token payload claims.
    """
    # Inline import breaks the top-level circular dependency loop cleanly
    from database import get_db

    # 1. Verify that the Authorization header credentials are present
    if credentials is None or credentials.credentials == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 2. Validate and decode token payload claims
    try:
        payload = jwt_manager.decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The provided authentication token is invalid or has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Extract user identifier (handles custom test tokens and standard JWT layouts)
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing a valid user identity claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Resolve the user from the async session generator context loop
    async for db in get_db():
        query = select(UserModel).where(UserModel.id == int(user_id))
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        break  # We only need the first yielding session instance

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user identity context could not be located.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
