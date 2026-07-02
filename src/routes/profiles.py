from datetime import date

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from security.http import get_token
from config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from database import get_db, UserModel, UserProfileModel, UserGroupEnum
from exceptions import TokenExpiredError, InvalidTokenError, S3FileUploadError
from schemas.profiles import ProfileResponse
from validation.profile import validate_image

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponse, status_code=201)
async def create_user_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str = Form(...),
    info: str | None = Form(None),
    avatar: UploadFile = File(...),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    db=Depends(get_db),
):
    # Verify token
    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    request_user_id = payload.get("user_id")
    if request_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    # Load requesting user and check active
    stmt_req = select(UserModel).where(UserModel.id == request_user_id).options(selectinload(UserModel.group))
    result_req = await db.execute(stmt_req)
    request_user = result_req.scalars().first()
    if not request_user or not request_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    # If creating for another user, ensure admin
    # group relationship is already loaded via selectinload to avoid lazy-loading IO
    if (
        request_user.id != user_id
        and request_user.group.name != UserGroupEnum.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # Ensure target user exists and is active
    stmt_target = select(UserModel).where(UserModel.id == user_id)
    result_target = await db.execute(stmt_target)
    target_user = result_target.scalars().first()
    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    # Check existing profile
    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result_profile = await db.execute(stmt_profile)
    existing_profile = result_profile.scalars().first()
    if existing_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    # Validate inputs
    try:
        # Use validation functions directly for names, gender and birth date
        from validation.profile import validate_name, validate_gender, validate_birth_date

        validate_name(first_name)
        validate_name(last_name)
        validate_gender(gender)
        # parse date
        dob = date.fromisoformat(date_of_birth)
        validate_birth_date(dob)

        if info is None or not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")

        # Validate avatar image
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # Upload avatar to S3
    avatar_key = f"avatars/{user_id}_avatar.jpg"
    try:
        file_bytes = await avatar.read()
        await s3_client.upload_file(avatar_key, file_bytes)
    except S3FileUploadError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to upload avatar. Please try again later.")

    # Create profile
    profile = UserProfileModel(
        first_name=first_name.lower(),
        last_name=last_name.lower(),
        gender=gender,
        date_of_birth=dob,
        info=info,
        avatar=avatar_key,
        user_id=user_id
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    avatar_url = await s3_client.get_file_url(avatar_key)

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "gender": profile.gender,
        "date_of_birth": str(profile.date_of_birth),
        "info": profile.info,
        "avatar": avatar_url,
    }
