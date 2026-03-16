from datetime import date

from PIL import Image
from fastapi import APIRouter, Form, UploadFile, File, Depends, HTTPException
from typing import Annotated

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import get_s3_storage_client, get_jwt_auth_manager
from database.models.accounts import UserProfileModel, GenderEnum
from exceptions import TokenExpiredError, InvalidTokenError, S3FileUploadError
from routes.accounts import get_user_by_id
from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from security.headers import api_key_header, validate_api_key
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    summary="Create user profile",
    description="Creation user profile with adding avatar",
    response_model=ProfileResponseSchema,
    status_code=201,
    dependencies=[Depends(validate_api_key)]
)
async def create_profile(
        user_id: int,
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: date = Form(),
        info: str = Form(),
        avatar: UploadFile = File(),
        access_token: Annotated[str | None, Depends(api_key_header)] = None,
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    try:
        ProfileRequestSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()[0]["msg"])
    try:
        decoded_auth_header = access_token.split()
        user_jwt = jwt_manager.decode_access_token(decoded_auth_header[1])
        current_user = await get_user_by_id(user_jwt["user_id"], db)
        query_user = await get_user_by_id(user_id, db)

        if not query_user or not query_user.is_active:
            raise HTTPException(status_code=401, detail="User not found or not active.")

        if query_user.profile:
            raise HTTPException(status_code=400, detail="User already has a profile.")

        if current_user.id != user_id and current_user.group_id == 1:
            raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

        try:
            avatar.file.seek(0)
            avatar_bytes = avatar.file.read()
            image = Image.open(avatar.file)
            image_format = image.format.lower()
            if image_format == "jpeg":
                image_format = "jpg"
            file_name = f"avatars/{user_id}_avatar.{image_format}"
            profile_db = UserProfileModel(
                first_name=first_name.lower(),
                last_name=last_name.lower(),
                gender=GenderEnum(gender),
                date_of_birth=date_of_birth,
                info=info,
                avatar=file_name,
                user=query_user
            )
            await s3_client.upload_file(file_name, avatar_bytes)
            avatar_url = await s3_client.get_file_url(file_name)

            db.add(profile_db)
            await db.commit()
            profile_db.avatar = avatar_url
            return profile_db
        except S3FileUploadError:
            raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
