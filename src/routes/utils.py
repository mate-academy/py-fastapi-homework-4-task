import aioboto3
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from security.interfaces import JWTAuthManagerInterface
from exceptions import BaseSecurityError, TokenExpiredError, InvalidTokenError
from config import get_jwt_auth_manager, get_settings, BaseAppSettings
from security import get_token


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    token = get_token(request)
    try:
        payload = jwt_manager.decode_access_token(token)
        print("Decoded payload:", payload)
        user_id = payload.get("user_id")
        print("Looking up user_id:", user_id)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return user_id


async def get_avatar_presigned_url(file_name: str):
    settings: BaseAppSettings = get_settings()
    session = aioboto3.Session(
        aws_access_key_id=settings.S3_STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.S3_STORAGE_SECRET_KEY,
    )
    async with session.client(
        "s3",
        endpoint_url=f"http://{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}",
    ) as s3:

        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": file_name},
            ExpiresIn=3600,
        )
        return url
