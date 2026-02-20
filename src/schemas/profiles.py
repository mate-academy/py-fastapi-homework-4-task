from datetime import date

from fastapi import UploadFile, File
from pydantic import BaseModel, field_validator, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    info: str | None = None
    avatar: UploadFile = File(None)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        validate_name(value)
        return value.lower()

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value):
        validate_name(value)
        return value.lower()

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value):
        validate_gender(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        validate_image(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        spaces_replaced = value.replace(" ", "")
        if not spaces_replaced:
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
