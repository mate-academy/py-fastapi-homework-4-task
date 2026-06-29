from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from database.models.accounts import UserModel, UserProfileModel, UserGroupEnum
from exceptions import S3FileUploadError
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema, get_profile_create_schema
from security.http import get_token
from config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
    user_id: int,
    profile_data: ProfileCreateSchema = Depends(get_profile_create_schema),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        token_data = jwt_manager.decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    requesting_user_id = token_data.get("user_id")

    # Check if the requesting user is an admin
    stmt_requester = select(UserModel).options(selectinload(UserModel.group)).where(UserModel.id == requesting_user_id)
    result_requester = await db.execute(stmt_requester)
    requesting_user = result_requester.scalars().first()

    is_admin = (
        requesting_user is not None
        and requesting_user.group is not None
        and requesting_user.group.name == UserGroupEnum.ADMIN
    )

    if requesting_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result_profile = await db.execute(stmt_profile)

    if result_profile.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        file_content = await profile_data.avatar.read()
        file_name = f"avatars/{user_id}_avatar.jpg"
        await s3_client.upload_file(file_name, file_content)
        avatar_url = await s3_client.get_file_url(file_name)
    except S3FileUploadError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name.lower(),
        last_name=profile_data.last_name.lower(),
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=file_name
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
        avatar=avatar_url
    )
