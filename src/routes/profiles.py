from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Header,
    Form,
    UploadFile,
    File,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import TokenExpiredError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="User Profile Creation",
    description="Create new user profile.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "User already has a profile.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User already has a profile.",
                    }
                }
            },
        },
        401: {
            "description": "User or token have invalid data.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authorization header is missing",
                    }
                }
            },
        },
        403: {
            "description": "User don't have permission to create this profile.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to edit this profile.",
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred during avatar uploading.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to upload avatar. Please try again later."
                    }
                }
            },
        },
    },
)
async def create_profile(
    user_id: int,
    first_name: str | None = Form(None),
    last_name: str | None = Form(None),
    gender: str | None = Form(None),
    date_of_birth: date | None = Form(None),
    info: str | None = Form(None),
    avatar: UploadFile | None = File(None),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> ProfileResponseSchema:
    """
    Endpoint for user profile creation.

    Creates a new profile for the specified user after validating the authorization token,
    checking whether the current user has permission to create the profile,
    and ensuring that the target user does not already have one.
    If an avatar file is provided, it is validated, uploaded to the storage service,
    and its storage key is saved in the profile data.

    Args:
        user_id (int): The ID of the user whose profile is being created.
        first_name (str | None): The user's first name from form data.
        last_name (str | None): The user's last name from form data.
        gender (str | None): The user's gender from form data.
        date_of_birth (date | None): The user's date of birth from form data.
        info (str | None): Additional profile information from form data.
        avatar (UploadFile | None): Optional avatar image uploaded with the profile form.
        s3_client (S3StorageInterface): Storage client used for uploading avatar files.
        db (AsyncSession): The asynchronous database session.
        authorization (str | None): The Authorization header containing the Bearer access token.
        jwt_manager (JWTAuthManagerInterface): The JWT manager used to decode and validate the access token.

    Returns:
        ProfileResponseSchema: The newly created user profile.

    Raises:
        HTTPException:
            - 400 Bad Request if the target user already has a profile.
            - 401 Unauthorized if the authorization header is missing, invalid,
              the token has expired, or the target user is not found / inactive.
            - 403 Forbidden if the current user does not have permission
              to create a profile for the specified user.
            - 422 Unprocessable Entity if the provided profile data or avatar file is invalid.
            - 500 Internal Server Error if an error occurs during avatar upload.
    """

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )

    token_user_id = payload.get("user_id")
    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.profile), selectinload(UserModel.group))
        .where(UserModel.id == token_user_id)
    )
    current_user = result.scalar_one_or_none()

    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    target_user = result.scalar_one_or_none()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if token_user_id != user_id and not current_user.has_group(UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    if target_user.profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    try:
        profile = ProfileRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
        )
    except ValidationError as e:
        msg = e.errors()[0]["msg"]
        if msg.startswith("Value error, "):
            msg = msg.removeprefix("Value error, ")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=msg,
        )

    if avatar is not None:
        try:
            validate_image(avatar)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        try:
            avatar_url = f"avatars/{user_id}_avatar.jpg"
            contents = await avatar.read()

            await s3_client.upload_file(file_name=avatar_url, file_data=contents)

            profile_data = profile.model_dump()
            profile_data["avatar"] = avatar_url
        except S3FileUploadError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later.",
            )
    else:
        avatar_url = None

    profile_data = profile.model_dump()
    profile_data["avatar"] = avatar_url

    new_profile = UserProfileModel(user_id=user_id, **profile_data)
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    response_data = ProfileResponseSchema.model_validate(new_profile).model_dump()

    if new_profile.avatar is not None:
        response_data["avatar"] = await s3_client.get_file_url(new_profile.avatar)

    return response_data
