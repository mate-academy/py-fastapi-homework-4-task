from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)
from fastapi import status


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def from_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ) -> "ProfileCreateSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )

    @field_validator("first_name")
    @classmethod
    def first_name_validator(cls, value):
        try:
            validate_name(value)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        return value.lower()

    @field_validator("last_name")
    @classmethod
    def last_name_validator(cls, value):
        try:
            validate_name(value)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        return value.lower()

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, avatar: UploadFile) -> UploadFile:
        try:
            validate_image(avatar)
            return avatar
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value_error",
                    "loc": ["avatar"],
                    "msg": str(e),
                    "input": avatar.filename
                }]
            )

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, gender: str) -> str:
        try:
            validate_gender(gender)
            return gender
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value_error",
                    "loc": ["gender"],
                    "msg": str(e),
                    "input": gender
                }]
            )

    @field_validator("date_of_birth")
    @classmethod
    def birth_date_validator(cls, value):
        try:
            validate_birth_date(value)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        return value

    @field_validator("info")
    @classmethod
    def info_validator(cls, value):
        if not value or not value.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Info field cannot be empty or contain only spaces."
            )
        return value.strip()


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[HttpUrl] = None
