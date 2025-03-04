from datetime import date
from typing import Optional

from fastapi import UploadFile, File
from pydantic import BaseModel, field_validator
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class BaseProfileSchema(BaseModel):
    user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[date]
    info: str

    model_config = {"from_attributes": True}

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, first_name: str) -> str:
        return validate_name(first_name)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, last_name: str) -> str:
        return validate_name(last_name)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date(cls, value: date) -> str:
        return validate_birth_date(value)


class AvatarUploadSchema(BaseModel):
    avatar: UploadFile = File(...)

    model_config = {"from_attributes": True}

    @field_validator("avatar")
    @classmethod
    def validate_image(cls, avatar: UploadFile) -> str:
        return validate_image(avatar)


class ProfileResponseSchema(BaseProfileSchema):
    id: int
    avatar: Optional[str]

    model_config = {"from_attributes": True}
