from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, HttpUrl, validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

class ProfileCreate(BaseModel):
    @validator("name")
    @classmethod
    def validate_name_field(cls, value):
        return validate_name(value)

    @validator("gender")
    @classmethod
    def validate_gender_field(cls, value):
        return validate_gender(value)

    @validator("date_of_birth")
    @classmethod
    def validate_birth_date_field(cls, value):
        return validate_birth_date(value)

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, value):
        return validate_image(value) if value else None


class ProfileResponseSchema(BaseModel):
    name: str = Field(..., description="User's name")
    gender: str = Field(..., description="User's gender")
    date_of_birth: date = Field(..., description="User's birth date")
    info: str
    avatar: UploadFile | None = None

    @field_validator("name")
    @classmethod
    def validate_name_field(cls, value):
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value):
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date_field(cls, value):
        return validate_birth_date(value)

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, value):
        return validate_image(value) if value else None
