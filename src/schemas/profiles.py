from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info,
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator(fields=["first_name", "last_name"])
    @classmethod
    def validate_a_name(cls, value: str) -> str:
        validate_name(value)

        return value.lower()

    @field_validator("gender")
    @classmethod
    def validate_a_gender(cls, value: str) -> str:
        validate_gender(value)

        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_a_date_of_birth(cls, value: date) -> date:
        validate_birth_date(value)

        return value

    @field_validator("info")
    @classmethod
    def validate_the_info(cls, value: str) -> str:
        validate_info(value)

        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)

        return value


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile
