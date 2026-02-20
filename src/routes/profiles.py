from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from services import minio_service
from src.database.models.accounts import UserProfileModel
from src.schemas.profiles import UserProfileCreate, UserProfileUpdate, UserProfileOut
from src.config.dependencies import get_async_session, get_current_user
from src.database.models.accounts import UserModel
from sqlalchemy import select

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/me", response_model=UserProfileOut)
async def read_profile(
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    profile = await session.get(UserProfileModel, current_user.profile.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@router.post("/", response_model=UserProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_in: UserProfileCreate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    existing_profile = await session.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    )
    if existing_profile.scalars().first():
        raise HTTPException(status_code=400, detail="Profile already exists")

    profile = UserProfileModel(**profile_in.dict(), user_id=current_user.id)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile

@router.patch("/me", response_model=UserProfileOut)
async def update_profile(
    profile_in: UserProfileUpdate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    profile = await session.get(UserProfileModel, current_user.profile.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for var, value in profile_in.dict(exclude_unset=True).items():
        setattr(profile, var, value)

    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile

@router.post("/me/avatar", response_model=UserProfileOut)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    profile = await session.get(UserProfileModel, current_user.profile.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    object_name = f"avatars/{current_user.id}_{file.filename}"
    avatar_url = await minio_service.upload_file(file, object_name)

    profile.avatar = avatar_url
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile
