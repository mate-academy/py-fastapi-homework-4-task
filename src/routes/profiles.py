
from fastapi import APIRouter, HTTPException
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

router = APIRouter()

s3 = boto3.client(
    "s3",
    aws_access_key_id="YOUR_AWS_ACCESS_KEY",
    aws_secret_access_key="YOUR_AWS_SECRET_KEY",
    region_name="YOUR_REGION"
)
BUCKET_NAME = "your-bucket"


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201
)
async def create_user_profile(
        user_id: int,
        data: ProfileRequestSchema,
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        file: UploadFile = File(...),
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

    if not data.avatar.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File is not an image")

    filename = f"user_{user_id}.jpg"
    contents = await file.read()

    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=contents, ContentType=file.content_type)
        avatar_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=data.first_name,
        last_name=data.last_name,
        avatar=avatar_url,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        info=data.info,
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return ProfileResponseSchema.model_validate(new_profile)
