from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl

    class Config:
        from_attributes = True


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_user(cls, value):
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_gender_user(cls, value):
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_user(cls, value):
        return validate_birth_date(value)

    @field_validator("avatar")
    @classmethod
    def validate_avatar_user(cls, value):
        return validate_image(value)

    @field_validator("info")
    @classmethod
    def validate_info_user(cls, value):
        if not value or not value.strip():
            raise ValueError("Info cannot be empty or consist only of spaces.")
        return value