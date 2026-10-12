from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, value: str):
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: str):
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def birth_date(cls, value: date):
        return validate_birth_date(value)

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str):
        if not value or not value.strip():
            raise ValueError("Info cannot be empty or contain only spaces")
        return value

    @field_validator("avatar")
    @classmethod
    def check_image(cls, value):
        return validate_image(value)

    class Config:
        from_attributes = True


class ProfileResponseSchema(ProfileSchema):
    id: int
    user_id: int

    class Config:
        from_attributes = True
