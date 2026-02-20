from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager, get_s3_storage_client
from database import get_db, UserGroupModel, UserModel, UserGroupEnum, UserProfileModel
from exceptions import BaseSecurityError, BaseS3Error
from schemas.profiles import ProfileResponseSchema, ProfileCreationRequestSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201,
    summary="Create a user profile",
    description="Create a user profile using a JWT token",
)
async def create_user_profile(
    user_id: int,
    profile_data: ProfileCreationRequestSchema = Depends(
        ProfileCreationRequestSchema.from_form
    ),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    async with db as session:
        try:
            token_data = jwt_manager.decode_access_token(token)
            decoded_user_id = token_data["user_id"]
        except BaseSecurityError as error:
            raise HTTPException(status_code=401, detail=str(error))

        # check if decoded user is current user
        if decoded_user_id != user_id:
            # if he is not a current user check his group
            stmt = (
                select(UserGroupModel)
                .join(UserModel)
                .where(UserModel.id == decoded_user_id)
            )
            result = await session.execute(stmt)
            user_group = result.scalars().first()
            # if his group is not admin raises exception
            if user_group.name != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to edit this profile.",
                )

        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await session.execute(stmt)
        user = result.scalars().first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail="User not found or not active.",
            )

        profile_stmt = select(UserProfileModel).where(
            UserProfileModel.user_id == user.id
        )
        profile_result = await session.execute(profile_stmt)
        profile_exist = profile_result.scalars().first()
        if profile_exist:
            raise HTTPException(
                status_code=400,
                detail="User already has a profile.",
            )

        try:
            avatar_file_name = f"avatars/{user_id}_avatar.jpg"
            avatar_data = await profile_data.avatar.read()
            await s3_client.upload_file(
                file_name=avatar_file_name, file_data=avatar_data
            )
        except BaseS3Error:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload avatar. Please try again later.",
            )

        profile = UserProfileModel(
            user_id=user.id,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            gender=profile_data.gender,
            date_of_birth=profile_data.date_of_birth,
            info=profile_data.info,
            avatar=avatar_file_name,
        )

        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        avatar_url = await s3_client.get_file_url(file_name=avatar_file_name)

        return ProfileResponseSchema(
            id=profile.id,
            user_id=profile.user_id,
            first_name=profile.first_name,
            last_name=profile.last_name,
            gender=profile.gender,
            date_of_birth=profile.date_of_birth,
            info=profile.info,
            avatar=avatar_url,
        )
