from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile


    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: str) -> None:
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date) -> None:
        return validate_birth_date(value)

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: UploadFile) -> None:
        return validate_image(value)

ProfileResponseSchema
