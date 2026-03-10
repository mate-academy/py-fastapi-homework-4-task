import datetime
from datetime import date
from typing import Any
from typing_extensions import Self

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


# Write your code here
class UserProfileBase(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_fullname(cls, value):
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value):
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_bdate(cls, value):
        return validate_birth_date(value)

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        if not value.strip():
            raise ValueError(
                "Info cannot be empty or consist only of spaces."
            )
        return value


class ProfileCreateRequestSchema(UserProfileBase):
    avatar: UploadFile

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        return validate_image(value)


class ProfileResponseSchema(UserProfileBase):
    id: int
    user_id: int
    avatar: str

    model_config = ConfigDict(from_attributes=True)
