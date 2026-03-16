from datetime import date
from typing import Any

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict
from typing_extensions import Self

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)
from validation.profile import validate_info


class ProfileBaseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str


class ProfileRequestSchema(ProfileBaseSchema):
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_first_last_name(cls, value):
        validate_name(value)
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        validate_info(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        validate_image(value)
        return value


class ProfileResponseSchema(ProfileBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    avatar: str
