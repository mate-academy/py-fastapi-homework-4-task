from fastapi import (
    APIRouter,
    Request,
    status,
    Depends,
    HTTPException,
)

from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_settings, get_s3_storage_client
from database import get_db, UserModel
from database.models.accounts import UserProfileModel
from exceptions import TokenExpiredError, S3ConnectionError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from storages import S3StorageInterface


router = APIRouter()
jwt_manager = get_jwt_auth_manager(settings=get_settings())


def get_access_token_data(request: Request) -> dict | None:
    authorization = request.headers.get("Authorization")
    scheme, credentials = get_authorization_scheme_param(authorization)
    if not (authorization and scheme and credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )
    try:
        payload = jwt_manager.decode_access_token(credentials)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )
    return payload


async def get_user_by_id(user_id: int, db: AsyncSession) -> UserModel | None:
    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.group), selectinload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> UserModel:
    payload = get_access_token_data(request)
    user_id = payload.get("user_id")
    db_user = await get_user_by_id(user_id, db)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return db_user


def normalize_profile_data(
    first_name: str, last_name: str, info: str
) -> tuple[str, str, str]:
    return (
        first_name.strip().lower(),
        last_name.strip().lower(),
        info.strip(),
    )


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Profile Creation",
    description="Create a new user profile with names, gender, date of birth, info, and avatar.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "Bad Request - The user's profile already exists.",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a profile."}
                },
            },
        },
        401: {
            "description": "Unauthorized - The authorization token is missing, invalid or expired."
            " Also, if there is an attempt to create a profile "
            "for non-existent or inactive user.",
            "content": {
                "application/json": {
                    "examples": {
                        "token_is_missing": {
                            "summary": "Token is missing",
                            "value": {"detail": "Authorization header is missing"},
                        },
                        "invalid_email_or_token": {
                            "summary": "Invalid Email or Token",
                            "value": {"detail": "Invalid email or token."},
                        },
                        "expired_token": {
                            "summary": "Expired Token",
                            "value": {"detail": "Invalid email or token."},
                        },
                        "invalid_user_for_profile": {
                            "summary": "Cannot create profile for given user.",
                            "value": {"detail": "User not found or not active."},
                        },
                    }
                }
            },
        },
        404: {
            "description": "Not Found - Current user is not found.",
            "content": {"application/json": {"example": {"detail": "User not found"}}},
        },
        500: {
            "description": "Internal Server Error - An error occurred during profile creation.",
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
async def create_user_profile(
    user_id: int,
    profile_data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    """
       User profile creation endpoint.

       Creates a profile for the current user if no profile exists yet.
       If successful, creates a new profile for that user and attaches it to them in db.

       Args:
           user_id (int): User ID provided in the URL.
           profile_data (ProfileRequestSchema): Request data for profile creation.
           current_user (UserModel): The authenticated user.
           db (AsyncSession): The asynchronous database session.
           s3_client (S3StorageInterface): The S3 storage client to save the user's avatar.

       Returns:
           ProfileResponseSchema: A response containing the profile data including
           its user's ID and avatar link.

       Raises:
           HTTPException:
               - 401 Bad Request if the user's profile already exists.
               - 403 Forbidden if the user's token is non-existent, not valid, expired,
               or the user's id does not match the URL ID.
               - 404 Not Found if current user is not found in db.
               - 500 Internal Server Error if an error occurs during profile creation.
       """
    if current_user.id != user_id and current_user.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    profile_user = await get_user_by_id(user_id, db)
    if not profile_user or not profile_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    if profile_user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar = profile_data.avatar
    avatar_file_name = f"avatars/{user_id}_{avatar.filename}"
    avatar_contents = await avatar.read()
    try:
        await s3_client.upload_file(
            file_name=avatar_file_name, file_data=avatar_contents
        )
        avatar_link = await s3_client.get_file_url(avatar_file_name)
    except (S3ConnectionError, S3FileUploadError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_file_name,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_link,
    )
