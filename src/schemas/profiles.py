from datetime import date
from pydantic import BaseModel, field_validator
from fastapi import UploadFile

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        return validate_name(v)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        return validate_name(v)

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, v: str) -> str:
        return validate_gender(v)

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date_field(cls, v: date) -> date:
        return validate_birth_date(v)

    @field_validator("info")
    @classmethod
    def validate_info(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Info cannot be empty")
        return v.strip()

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, v: UploadFile) -> UploadFile:
        return validate_image(v)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
