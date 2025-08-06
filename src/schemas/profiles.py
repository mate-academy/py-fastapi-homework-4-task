from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation.profile import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileResponseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    @field_validator('first_name')
    @classmethod
    def validate_first_name(cls, v):
        return validate_name(v)

    @field_validator('last_name')
    @classmethod
    def validate_last_name(cls, v):
        return validate_name(v)

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v):
        return validate_gender(v)

    @field_validator('date_of_birth')
    @classmethod
    def validate_date_of_birth(cls, v):
        return validate_birth_date(v)

    @field_validator('avatar')
    @classmethod
    def validate_avatar(cls, v):
        return validate_image(v)
