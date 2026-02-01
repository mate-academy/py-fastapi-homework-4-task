from datetime import date
from typing import Annotated

from fastapi import APIRouter, Request, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.params import Depends, Form, File
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import select

import schemas
from config import get_jwt_auth_manager, get_s3_storage_client
import database
from exceptions import TokenExpiredError, InvalidTokenError, BaseS3Error
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface


router = APIRouter()


def profile_form(
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
) -> schemas.ProfileCreateSchema:
    try:
        return schemas.ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )
    except ValidationError as e:
        errors = []
        for err in e.errors():
            err.pop("input", None)
            errors.append(err)

        raise RequestValidationError(errors)


async def get_authorization(
        request: Request,
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(database.get_db)) -> database.UserModel:
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    try:
        scheme, token = token.split()
        if scheme.lower() != "bearer":
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    try:
        data = jwt_manager.decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>")
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")

    user_id = data.get("user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    query = select(
        database.UserModel
    ).options(
        joinedload(database.UserModel.group)
    ).where(database.UserModel.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")
    return user


@router.post("/users/{user_id}/profile/", response_model=schemas.ProfileResponseSchema, status_code=201)
async def create_profile(
        user_id: int,
        data: Annotated[schemas.ProfileCreateSchema, Depends(profile_form)],
        r_user: database.UserModel = Depends(get_authorization),
        db: AsyncSession = Depends(database.get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):

    if r_user.group.name != "admin" and r_user.id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    query = select(database.UserModel).options(
        joinedload(database.UserModel.profile)
    ).where(database.UserModel.id == user_id)
    result = await db.execute(query)
    p_user = result.scalar_one_or_none()

    if not p_user or not p_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    if p_user.profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    file_data = await data.avatar.read()
    file_name = f"avatars/{p_user.id}_{data.avatar.filename}"
    try:
        await s3_client.upload_file(file_name=file_name, file_data=file_data)
    except BaseS3Error:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")
    profile = database.UserProfileModel(
        first_name=data.first_name,
        last_name=data.last_name,
        avatar=file_name,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        info=data.info,
        user=p_user,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return schemas.ProfileResponseSchema(
        id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        avatar=profile.avatar,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
    )
