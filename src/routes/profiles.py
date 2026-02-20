from fastapi import HTTPException, APIRouter, Header, Depends, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserProfileModel, UserModel
from exceptions import TokenExpiredError, InvalidTokenError

from schemas.profiles import ProfileResponse, ProfileCreate
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


async def get_current_user(
        authorization: str = Header(..., alias="Authorization"),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db)
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token."
        )

    result = await db.execute(select(UserModel).where(UserModel.email == payload["sub"]))
    current_user = result.scalar_one_or_none()
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )
    return current_user


@router.post("/users/{user_id}/profile/",
             response_model=ProfileResponse,
             status_code=status.HTTP_201_CREATED
             )
async def create_profile(
        user_id: int,
        profile_data: ProfileCreate,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
) -> ProfileResponse:
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )
    if current_user.id != user_id and current_user.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )
    existing_profile = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if existing_profile.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )
    try:
        avatar_url = await s3_client.upload(profile_data.avatar, f"{user_id}_avatar.jpg")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_url
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return ProfileResponse.model_validate(new_profile)
