from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl
from database.models.accounts import GenderEnum

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def check_names(cls, value: str) -> str:
        validate_name(value)

        return value.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def check_gender(cls, value: str) -> str:
        validate_gender(value)

        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date) -> date:
        validate_birth_date(value)

        return value

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)

        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")

        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl
