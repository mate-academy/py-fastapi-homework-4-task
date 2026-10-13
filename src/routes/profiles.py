from jose import ExpiredSignatureError, JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from schemas.profiles import ProfileResponseSchema, ProfileSchema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from storages import S3StorageClient
from security.token_manager import JWTAuthManagerInterface
from config import get_s3_storage_client, get_jwt_auth_manager

from database import (
    get_db,
    UserModel,
    UserProfileModel,
)

router = APIRouter()


def verify_auth_header(request: Request):
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )
    bearer = authorization.split()
    if len(bearer) != 2 or bearer[0] != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
    return bearer[1]


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    description="Create user profile",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_auth_header)]
)
async def profile_user(
        user_id: int,
        user_data: ProfileSchema = Depends(ProfileSchema.as_form),
        s3_client: S3StorageClient = Depends(get_s3_storage_client),
        token: str = Depends(verify_auth_header),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except Exception as e:
        if e.__class__.__name__ == "TokenExpiredError" or "expired" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    token_user_id = payload.get("user_id")

    # 1. Шукаємо того, хто робить запит (з токена)
    stmt_requester = select(UserModel).where(UserModel.id == token_user_id)
    requester_res = await db.execute(stmt_requester)
    requester = requester_res.scalar_one_or_none()

    if not requester:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User from token not found")

    # 2. Перевіряємо, чи він адмін (група 3)
    is_admin = requester.group_id == 3

    if token_user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # 3. Шукаємо цільового користувача, якому створюють профіль
    search_user = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(search_user)
    db_user = result.scalar_one_or_none()

    if db_user is None or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active.")

    profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result_profile = await db.execute(profile)
    user_profile = result_profile.scalar_one_or_none()

    if user_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    file_key = f"avatars/{user_id}_avatar.jpg"

    try:
        avatar = await user_data.avatar.read()
        await s3_client.upload_file(
            file_name=file_key,
            file_data=avatar,
        )

        avatar_url = await s3_client.get_file_url(file_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    user_profile_model = UserProfileModel(
        user_id=user_id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        gender=user_data.gender,
        date_of_birth=user_data.date_of_birth,
        info=user_data.info,
        avatar=file_key,
    )

    db.add(user_profile_model)
    await db.commit()
    await db.refresh(user_profile_model)

    user_profile_model.avatar = avatar_url
    return user_profile_model
