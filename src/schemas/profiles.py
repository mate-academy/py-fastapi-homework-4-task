from datetime import date
from enum import Enum
from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, Field, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class GenderEnum(str, Enum):
    MAN = "man"
    WOMAN = "woman"
    OTHER = "other"


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(min_length=1, max_length=50),
    last_name: str = Field(min_length=1, max_length=50),
    gender: GenderEnum
    date_of_birth: date
    info: Field(None, min_length=1, max_length=1000)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_field(cls, value: str) -> str:
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, value: str) -> str:
        return validate_birth_date(value)

    @field_validator("info")
    @classmethod
    def validate_info_field(cls, value: str) -> str:
        if value is not None:
            if not value.strip():
                raise ValueError("Info cannot be empty or consist only of spaces.")
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str = None
    avatar: str = None

    class Config:
        from_attributes = True
