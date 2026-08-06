from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class UserProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile = File(...)

    @field_validator("first_name", mode="before")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("last_name", mode="before")
    @classmethod
    def validate_last_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth", mode="after")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
        return value


class UserProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: str
    info: str
    avatar: HttpUrl
