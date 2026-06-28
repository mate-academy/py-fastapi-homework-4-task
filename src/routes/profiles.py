from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from config import get_s3_storage_client, get_jwt_auth_manager
from database import UserProfileModel, UserModel, UserGroupEnum, get_db
from exceptions import TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileCreateSchema
from security.http import get_token
from storages import S3StorageInterface
from validation.profile import validate_image


router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileCreateSchema, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
        user_id: int,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: str = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(None),
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager=Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except (TokenExpiredError, InvalidTokenError):
        raise HTTPException(status_code=401, detail="Token has expired.")
    token_user_id = int(payload.get("user_id"))
    result_requester = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == token_user_id)
    )
    requester = result_requester.scalar_one_or_none()
    result = await db.execute(
        select(UserModel)
        .where(UserModel.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")
    if token_user_id != user_id and (not requester or requester.group.name != UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=403, detail="You don't have permission to edit this profile."
        )
    result_profile = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    profile = result_profile.scalar_one_or_none()
    if profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")
    from datetime import date
    try:
        birth_date = date.fromisoformat(date_of_birth)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format.")
    from validation.profile import validate_name, validate_gender, validate_birth_date
    from database.models.accounts import GenderEnum
    try:
        validate_name(first_name)
        validate_name(last_name)
        validate_gender(gender)
        validate_birth_date(birth_date)
        if not info or not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if avatar:
        try:
            validate_image(avatar)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        avatar_url_for_response = None
        avatar_key_for_db = None
        if avatar:
            try:
                avatar_filename = f"avatars/{user_id}_avatar.jpg"
                content = await avatar.read()
                await s3_client.upload_file(avatar_filename, content)
                avatar_key_for_db = avatar_filename
                avatar_url_for_response = await s3_client.get_file_url(avatar_filename)
            except Exception:
                raise HTTPException(
                    status_code=500, detail="Failed to upload avatar. Please try again later."
                )
        new_profile = UserProfileModel(
            first_name=first_name.lower(),
            last_name=last_name.lower(),
            gender=GenderEnum[gender.upper()],
            date_of_birth=birth_date,
            info=info,
            avatar=avatar_key_for_db,
            user_id=user_id,
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        return ProfileCreateSchema(
            id=new_profile.id,
            user_id=new_profile.user_id,
            first_name=new_profile.first_name,
            last_name=new_profile.last_name,
            gender=new_profile.gender,
            date_of_birth=new_profile.date_of_birth,
            info=new_profile.info,
            avatar=avatar_url_for_response
        )
