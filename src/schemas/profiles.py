from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, HttpUrl, field_validator

from database.models.accounts import GenderEnum
from validation import (
    validate_birth_date,
    validate_gender,
    validate_image,
    validate_name,
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("gender")
    @classmethod
    def validate_profile_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_profile_birth_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_profile_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    avatar: HttpUrl
    gender: GenderEnum
    date_of_birth: date
    info: str
    user_id: int

    model_config = {
        "from_attributes": True
    }
