from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import ValidationError

from config import get_jwt_auth_manager, get_s3_storage_client, get_settings, BaseAppSettings
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import BaseSecurityError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token
from storages.interfaces import S3StorageInterface
from validation import validate_image

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create User Profile",
    description=(
            "<h3>Create a user profile with personal information and avatar.</h3>"
            "<p>This endpoint allows authenticated users to create their profile. "
            "The request must include first name, last name, gender, date of birth, "
            "additional info, and an avatar image.</p>"
    ),
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Profile created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "user_id": 1,
                        "first_name": "john",
                        "last_name": "doe",
                        "gender": "man",
                        "date_of_birth": "1990-01-01",
                        "info": "This is a test profile.",
                        "avatar": "http://minio-theater/avatars/1_avatar.jpg"
                    }
                }
            },
        },
        400: {
            "description": "Bad Request - User already has a profile.",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a profile."}
                }
            },
        },
        401: {
            "description": "Unauthorized - Invalid or missing token, or user not found.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_token": {
                            "summary": "Missing Authorization Header",
                            "value": {"detail": "Authorization header is missing"}
                        },
                        "invalid_format": {
                            "summary": "Invalid Token Format",
                            "value": {"detail": "Invalid Authorization header format. Expected 'Bearer <token>'"}
                        },
                        "expired_token": {
                            "summary": "Token Expired",
                            "value": {"detail": "Token has expired."}
                        },
                        "user_not_found": {
                            "summary": "User Not Found",
                            "value": {"detail": "User not found or not active."}
                        }
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - User doesn't have permission to create this profile.",
            "content": {
                "application/json": {
                    "example": {"detail": "You don't have permission to edit this profile."}
                }
            },
        },
        422: {
            "description": "Unprocessable Entity - Validation error in input data.",
            "content": {
                "application/json": {
                    "example": {"detail": "Validation error details"}
                }
            },
        },
        500: {
            "description": "Internal Server Error - Failed to upload avatar or create profile.",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to upload avatar. Please try again later."}
                }
            },
        },
    }
)
async def create_profile(
        user_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        settings: BaseAppSettings = Depends(get_settings),
) -> ProfileResponseSchema:
    """
    Create a user profile with personal information and avatar.

    This endpoint handles profile creation for authenticated users. It performs
    several validation checks in the following order:
    1. Token validation (Bearer token must be present and valid)
    2. Authorization (users can only create their own profile unless they're admins)
    3. User existence and active status
    4. Check if profile already exists
    5. Parse and validate form data (text fields)
    6. Avatar image validation (format and size)
    7. Upload avatar to S3 storage
    8. Create profile in database

    Args:
        user_id: The ID of the user for whom the profile is being created
        request: FastAPI request object
        db: Database session
        jwt_manager: JWT authentication manager
        s3_client: S3 storage client for avatar upload
        settings: Application settings

    Returns:
        ProfileResponseSchema: The created profile with all details

    Raises:
        HTTPException:
            - 401 if token is missing, invalid, or expired
            - 401 if user not found or not active
            - 403 if user doesn't have permission to create this profile
            - 400 if user already has a profile
            - 422 if validation fails (text fields or avatar)
            - 500 if avatar upload fails or profile creation fails
    """
    # Step 1: Extract and validate the Bearer token
    try:
        token = get_token(request)
    except HTTPException:
        raise

    # Step 2: Decode the token and extract user_id
    try:
        decoded_token = jwt_manager.decode_access_token(token)
        authenticated_user_id = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error)
        )

    # Step 3: Check if trying to create profile for another user
    # If yes, we need to verify admin/moderator permissions
    needs_permission_check = (authenticated_user_id != user_id)

    if needs_permission_check:
        # Load user with group to check permissions
        stmt = select(UserModel).options(selectinload(UserModel.group)).where(UserModel.id == authenticated_user_id)
        result = await db.execute(stmt)
        authenticated_user = result.scalars().first()

        if not authenticated_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )

        # Check if user has elevated permissions
        if authenticated_user.group.name not in [UserGroupEnum.ADMIN.value, UserGroupEnum.MODERATOR.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

        # For admin/moderator creating another user's profile, check target user exists
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await db.execute(stmt)
        target_user = result.scalars().first()

        if not target_user or not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )
    # If user is creating their own profile, we'll check existence later (after validation)

    # Step 4: Check if the user already has a profile (only if we already verified user exists)
    if needs_permission_check:
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        result = await db.execute(stmt)
        existing_profile = result.scalars().first()

        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a profile."
            )

    # Step 5: Parse form data manually AFTER authentication checks
    form_data = await request.form()

    # Extract form fields
    first_name = form_data.get("first_name")
    last_name = form_data.get("last_name")
    gender = form_data.get("gender")
    date_of_birth_str = form_data.get("date_of_birth")
    info = form_data.get("info")
    avatar = form_data.get("avatar")

    # Convert date_of_birth from string to date
    try:
        if isinstance(date_of_birth_str, str):
            date_of_birth = date.fromisoformat(date_of_birth_str)
        else:
            date_of_birth = date_of_birth_str
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid date format. Expected YYYY-MM-DD."
        )

    # Step 6: Validate text fields using ProfileCreateSchema
    try:
        profile_data = ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info
        )
    except ValidationError as e:
        # Extract the first validation error message
        error_messages = []
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            msg = error.get("msg", "Validation error")
            error_messages.append(f"{field}: {msg}")

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_messages[0] if error_messages else "Validation error"
        )

    # Step 7: Validate the avatar image
    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    # Step 8: NOW check if user creating own profile exists (after validation)
    if not needs_permission_check:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await db.execute(stmt)
        target_user = result.scalars().first()

        if not target_user or not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or not active."
            )

        # Also check if profile already exists
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        result = await db.execute(stmt)
        existing_profile = result.scalars().first()

        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a profile."
            )

    # Step 9: Upload avatar to S3 storage
    try:
        # Generate a unique filename for the avatar
        file_extension = avatar.filename.split(".")[-1] if "." in avatar.filename else "jpg"
        avatar_filename = f"{user_id}_avatar.{file_extension}"
        avatar_key = f"avatars/{avatar_filename}"

        # Upload to S3
        avatar_content = await avatar.read()
        await s3_client.upload_file(
            file_name=avatar_key,
            file_data=avatar_content
        )
    except S3FileUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # Step 10: Create the profile in the database
    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=profile_data.first_name.lower(),
            last_name=profile_data.last_name.lower(),
            gender=profile_data.gender,
            date_of_birth=profile_data.date_of_birth,
            info=profile_data.info,
            avatar=avatar_key  # Store the S3 key, not the full URL
        )

        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)

        return ProfileResponseSchema.model_validate(new_profile)

    except SQLAlchemyError as error:
        await db.rollback()
        # If profile creation fails, we should try to clean up the uploaded avatar
        try:
            await s3_client.delete_file(avatar_key)
        except:
            pass  # If cleanup fails, log it but don't raise another error

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile. Please try again later."
        )
