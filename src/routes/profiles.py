from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from config.dependencies import get_s3_storage_client, get_settings
from config.settings import Settings
from database.models.accounts import UserGroupEnum, UserGroupModel, UserModel, UserProfileModel
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema, get_profile_form
from security.http import get_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db


from jose import ExpiredSignatureError, JWTError, jwt

from storages.interfaces import S3StorageInterface
from validation.profile import validate_image

router = APIRouter()

@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema)
async def profile_create(
    user_id: int,
    request: Request,
    user_profile_data: ProfileRequestSchema = Depends(get_profile_form),
    avatar: UploadFile = File(),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    token = get_token(request=request)
    try:
        # Decode the JWT token to get the payload
        payload = jwt.decode(
            token,
            settings.SECRET_KEY_ACCESS,
            algorithms=[settings.JWT_SIGNING_ALGORITHM]
        )

        result_user = await db.execute(select(UserModel).where(UserModel.id == user_id))
        db_user = result_user.scalar_one_or_none()
        if not db_user or db_user.is_active == False:
            raise HTTPException(status_code=401, detail="User not found or not active.")

        stmt_group = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.ADMIN)
        result = await db.execute(stmt_group)
        admin_group = result.scalars().first()
        is_admin = db_user.group_id == admin_group.id if admin_group else False
        if not is_admin:
            raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

        result_user_profile = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
        user_profile = result_user_profile.first()
        if user_profile:
            raise HTTPException(status_code=400, detail="User already has a profile.")

        validate_image(avatar)
        filename = f"user_{user_id}.jpg"
        contents = await avatar.read()
        await s3_client.upload_file(file_name=filename, file_data=contents)
        avatar_url = f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{filename}"
    
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=user_profile_data.first_name,
        last_name=user_profile_data.last_name,
        avatar=avatar_url,
        gender=user_profile_data.gender,
        date_of_birth=user_profile_data.date_of_birth,
        info=user_profile_data.info,
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return new_profile