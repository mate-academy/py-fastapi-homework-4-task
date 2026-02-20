from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.dependencies import get_jwt_auth_manager
from src.exceptions.security import TokenExpiredError
from src.security.http import get_token

from src.database.models.accounts import UserModel, UserProfileModel
from database import get_db
from src.schemas.profiles import ProfileResponseSchema, ProfileRequestSchema
from src.security.interfaces import JWTAuthManagerInterface
import boto3
import os

router = APIRouter()


def get_s3_storage_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
    )


BUCKET_NAME = "your-bucket"


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201
)
async def create_user_profile(
        user_id: int,
        first_name: Annotated[str] = Form(...),
        last_name: Annotated[str] = Form(...),
        gender: Annotated[str] = Form(...),
        birth_date: Annotated[str] = Form(...),
        info: Annotated[str] = Form(...),
        avatar: UploadFile = File(...),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3=Depends(get_s3_storage_client),
):
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired."
        )

    token_user_id = decoded_token.get("user_id")

    requester_stmt = select(UserModel).where(UserModel.id == token_user_id)
    requester_result = await db.execute(requester_stmt)
    requester = requester_result.scalar_one_or_none()

    if not requester or not requester.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    target_stmt = select(UserModel).where(UserModel.id == user_id)
    target_result = await db.execute(target_stmt)
    target_user = target_result.scalar_one_or_none()

    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    profile_stmt = (select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if profile:
        raise HTTPException(
            status_code=400,
            detail="User already has a profile."
        )

    if token_user_id != user_id and (requester.group.name in {"user", "moderator"}):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile."
        )

    if not avatar.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File is not an image")

    filename = f"user_{user_id}.jpg"
    contents = await avatar.read()

    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=filename,
            Body=contents,
            ContentType=avatar.content_type
        )
        avatar_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        avatar=avatar_url,
        gender=gender,
        birth_date=birth_date,
        info=info,
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return ProfileResponseSchema.model_validate(new_profile)
