from datetime import date

from fastapi import (
    APIRouter, Depends, UploadFile, HTTPException, status, Request
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel
from exceptions import BaseSecurityError
from schemas.profiles import ProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(  # noqa: C901
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):

    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    try:
        decoded = jwt_manager.decode_access_token(token)
        token_user_id = decoded.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=401, detail=str(e))

    form = await request.form()
    first_name = form.get("first_name")
    last_name = form.get("last_name")
    gender = form.get("gender")
    date_of_birth = form.get("date_of_birth")
    info = form.get("info")
    avatar: UploadFile = form.get("avatar")

    if not all([first_name, last_name, gender, date_of_birth, avatar]):
        raise HTTPException(status_code=422, detail="Missing required form fields.")

    if info is None or not info.strip():
        raise HTTPException(
            status_code=422,
            detail="Info field cannot be empty or contain only spaces.",
        )

    try:

        validated_first_name = validate_name(first_name)
        if validated_first_name is not None:
            first_name = validated_first_name

        validated_last_name = validate_name(last_name)
        if validated_last_name is not None:
            last_name = validated_last_name

        validate_gender(gender)

        try:
            date_of_birth_obj = date.fromisoformat(date_of_birth)
        except ValueError as e:

            raise HTTPException(status_code=422, detail=str(e))
        validate_birth_date(date_of_birth_obj)

        validate_image(avatar)
    except HTTPException:

        raise
    except Exception as e:

        raise HTTPException(status_code=422, detail=str(e))

    stmt_user = (
        select(UserModel)
        .options(selectinload(UserModel.group))
        .filter_by(id=user_id)
    )
    result_user = await db.execute(stmt_user)
    target_user = result_user.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not target_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    stmt_token_user = (
        select(UserModel)
        .options(selectinload(UserModel.group))
        .filter_by(id=token_user_id)
    )
    result_token_user = await db.execute(stmt_token_user)
    token_user = result_token_user.scalars().first()

    if not token_user or not token_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    is_admin = bool(token_user.group and token_user.group.name == "admin")

    if token_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile.",
        )

    stmt_profile = select(UserProfileModel).filter_by(user_id=user_id)
    result_profile = await db.execute(stmt_profile)
    existing_profile = result_profile.scalars().first()
    if existing_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    try:

        ext = (avatar.filename or "").split(".")[-1] if avatar.filename else "jpg"
        avatar_key = f"avatars/{user_id}_avatar.{ext}"
        file_bytes = await avatar.read()
        await s3_client.upload_file(avatar_key, file_bytes)
        avatar_url = await s3_client.get_file_url(avatar_key)
    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth_obj,
        info=info.strip(),
        avatar=avatar_url,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=str(profile.gender) if hasattr(profile.gender, "value") else profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=profile.avatar,
    )
