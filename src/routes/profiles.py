from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security.utils import get_authorization_scheme_param
from schemas import ProfileResponseSchema, UserProfileCreateRequestSchema
from database import get_db, UserModel, UserProfileModel, UserGroupModel, UserGroupEnum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from security.token_manager import JWTAuthManagerInterface
from config import get_jwt_auth_manager, get_s3_storage_client
from exceptions import TokenExpiredError, InvalidTokenError
from storages import S3StorageInterface

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_db)]

JWTManager = Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)]


StorageInterface = Annotated[S3StorageInterface, Depends(get_s3_storage_client)]

UserProfileCreateData = Annotated[
    UserProfileCreateRequestSchema,
    Depends(UserProfileCreateRequestSchema.as_form),
]


def get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    scheme, token = get_authorization_scheme_param(authorization)

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
        )

    return token


BearerToken = Annotated[str, Depends(get_bearer_token)]


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    db: SessionDep,
    user_id: int,
    profile_data: UserProfileCreateData,
    jwt_manager: JWTManager,
    s3_client: StorageInterface,
    token: BearerToken,
):

    try:
        token_data = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )

    token_user_id = token_data.get("user_id")
    user = await db.scalar(select(UserModel).where(UserModel.id == user_id))
    token_user_group = await db.scalar(
        select(UserGroupModel.name)
        .join(UserModel, UserModel.group_id == UserGroupModel.id)
        .where(UserModel.id == token_user_id)
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )
    if token_user_id != user.id and token_user_group != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    profile = await db.scalar(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )
    file_name = f"avatars/{user_id}_avatar.jpg"
    try:
        file_data = await profile_data.avatar.read()
        await s3_client.upload_file(file_name=file_name, file_data=file_data)
        avatar_url = await s3_client.get_file_url(file_name=file_name)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )
    new_profile = UserProfileModel(
        **profile_data.model_dump(exclude={"avatar"}),
        avatar=file_name,
        user_id=user_id,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    profile_res = ProfileResponseSchema(
        **profile_data.model_dump(exclude={"avatar"}),
        id=new_profile.id,
        avatar=avatar_url,
        user_id=user.id,
    )
    return profile_res
