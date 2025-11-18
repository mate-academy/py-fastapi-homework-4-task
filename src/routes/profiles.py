from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    HTTPException,
    status,
    Request,
    Form,
    File,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserModel, UserProfileModel
from database.models.accounts import UserGroupModel, UserGroupEnum
from exceptions import BaseSecurityError
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: int,
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
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

    stmt_user = select(UserModel).filter_by(id=user_id)
    result_user = await db.execute(stmt_user)
    target_user = result_user.scalars().first()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active.",
        )

    stmt_token_user = select(UserModel).filter_by(id=token_user_id)
    result_token_user = await db.execute(stmt_token_user)
    token_user = result_token_user.scalars().first()

    if not token_user or not token_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    group_name = None
    if getattr(token_user, "group_id", None) is not None:
        stmt_group = select(UserGroupModel.name).where(
            UserGroupModel.id == token_user.group_id
        )
        group_result = await db.execute(stmt_group)
        group_name = group_result.scalar_one_or_none()

    is_admin = group_name == UserGroupEnum.ADMIN

    if token_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile.",
        )

    stmt_profile = select(UserProfileModel).filter_by(user_id=user_id)
    result_profile = await db.execute(stmt_profile)
    if result_profile.scalars().first():
        raise HTTPException(status_code=400, detail="User already has a profile.")

    profile_data = ProfileRequestSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
    )

    try:
        validate_image(avatar)

        ext = (avatar.filename or "").split(".")[-1]
        avatar_key = f"avatars/{user_id}_avatar.{ext}"

        file_bytes = await avatar.read()
        await s3_client.upload_file(avatar_key, file_bytes)
        avatar_url = await s3_client.get_file_url(avatar_key)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later.",
        )

    profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return profile
