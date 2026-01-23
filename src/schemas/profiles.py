from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, field_validator, ConfigDict

from src.validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class TokenData(BaseModel):
    user_id: str
    is_admin: bool = False


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("info")
    @classmethod
    def validate_info(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v.strip()

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v):
        validate_image(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v):
        validate_birth_date(v)
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        validate_gender(v)
        return v

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        validate_name(v)
        return v.lower()

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        validate_name(v)
        return v.lower()


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = ConfigDict(from_attributes=True)
