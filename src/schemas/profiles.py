from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError

from src.validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    @staticmethod
    def first_name_validator(value: str) -> str:
        validate_name(value)
        return value.strip().lower()

    @field_validator("last_name")
    @staticmethod
    def last_name_validator(value: str) -> str:
        validate_name(value)
        return value.strip().lower()

    @field_validator("gender")
    @staticmethod
    def gender_validator(value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @staticmethod
    def date_of_birth_validator(value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("avatar")
    @staticmethod
    def avatar_validator(value: str) -> UploadFile:
        validate_image(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info_field(cls, value):
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value.strip()


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True
    }
