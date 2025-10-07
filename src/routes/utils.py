from fastapi import Depends, HTTPException, status, Request, Security
from fastapi.security import HTTPBearer
from security.interfaces import JWTAuthManagerInterface
from exceptions import BaseSecurityError, TokenExpiredError, InvalidTokenError
from config import get_jwt_auth_manager
from security import get_token
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    credentials=Security(bearer_scheme),
):
    token = get_token(request)
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
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


async def validate_profile_data(
    first_name, last_name, gender, date_of_birth, info, avatar
):
    """Validate input fields and image."""
    if first_name:
        validate_name(first_name)
    if last_name:
        validate_name(last_name)
    if gender:
        validate_gender(gender)
    if date_of_birth:
        validate_birth_date(date_of_birth)
    if info is not None and not info.strip():
        raise ValueError("Info field cannot be empty or contain only spaces.")
    if avatar:
        validate_image(avatar)
