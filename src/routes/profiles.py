from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from database.models.accounts import UserProfileModel, UserModel, UserGroupEnum
from database.session_postgresql import get_postgresql_db
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema, GenderEnum
from security.interfaces import JWTAuthManagerInterface
from security.utils import generate_secure_token
from storages.interfaces import S3StorageInterface
from validation.profile import validate_image

router = APIRouter()


@router.post(
    "users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create user profile",
    description="Create a new user profile",
)
async def create_profile(
        user_id: int,
        first_name: str = Form(min_length=1, max_length=50),
        last_name: str = Form(min_length=1, max_length=50),
        gender: GenderEnum = Form(),
        date_of_birth: str = Form(),
        info: str = Form(None, min_length=1, max_length=1000),
        avatar: UploadFile = File(),
        db: AsyncSession = Depends(get_postgresql_db),
        token: str = Depends(generate_secure_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    decoded_token = await jwt_manager.decode_access_token(token)
    token_user_id = decoded_token.user_id
    token_user_group = decoded_token.user_group

    if token_user_id != user_id and token_user_group != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You dont have permission to perform this action",
        )
    user = await db.get(UserModel, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active"
        )

    existing_profile = await db.get(UserProfileModel, user_id)
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    profile_data_for_validatiom = {
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender.value,
        "date_of_birth": date_of_birth,
        "info": info,
    }
    try:
        ProfileCreateSchema(**profile_data_for_validatiom)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    try:
        image_content = await avatar.read()
        validate_image(avatar.filename, image_content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid avatar file {e}"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read avatar file"
        )

    avatar_path = f"avatars/{user_id}_avatar.jpg"
    try:
        await s3_client.upload_file(avatar_path, image_content)
        avatar_url = s3_client.get_file_url(avatar_path)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar_path
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    new_profile.avatar = avatar_url
    return ProfileResponseSchema.from_orm(new_profile)
