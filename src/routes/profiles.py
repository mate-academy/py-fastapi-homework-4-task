from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# from datetime import date
from pydantic import ValidationError

from database import get_db
from database.models.accounts import UserModel, UserProfileModel

from config.dependencies import get_jwt_auth_manager, get_s3_storage_client, get_token
from security.interfaces import JWTAuthManagerInterface
from storages.interfaces import S3StorageInterface
from schemas.profiles import ProfileCreateValidationModel, ProfileResponseSchema
from validation import validate_image

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/accounts/login")

router = APIRouter(prefix="/users", tags=["Profiles"])


@router.post("/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: str = Form(...),   # Якщо тест свариться на дату, спробувати str замість date
    info: str = Form(None),
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    auth_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        payload = auth_manager.decode_access_token(token)
        token_user_id = int(payload.get("sub"))
        user_group = payload.get("group", "USER")
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    if token_user_id != user_id and user_group != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    user_query = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = user_query.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    profile_query = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if profile_query.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    try:
        validated_data = ProfileCreateValidationModel(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info
        )
    except (ValidationError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    try:
        file_content = await avatar.read()
        s3_file_path = f"avatars/{user_id}_avatar.{avatar.filename.split('.')[-1]}"

        avatar_url = await s3_client.upload_file(
            s3_file_path,
            file_content
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        first_name=validated_data.first_name,
        last_name=validated_data.last_name,
        gender=validated_data.gender,
        date_of_birth=validated_data.date_of_birth,
        info=validated_data.info,
        avatar=avatar_url,
        user_id=user_id
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return new_profile
