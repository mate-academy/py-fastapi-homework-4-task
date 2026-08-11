from datetime import date

from fastapi import UploadFile, Form, File
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError

from database.models.accounts import GenderEnum

from validation import (
    validate_name,
    validate_gender as validate_gender_value,
    validate_image,
    validate_birth_date,
)


class BaseUserProfileSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        validate_name(value)
        return value.lower()

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value):
        validate_name(value)
        return value.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value):
        validate_gender_value(value)

        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value):
        validate_birth_date(value)
        return value


class UserProfileCreateRequestSchema(BaseUserProfileSchema):
    avatar: UploadFile

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        validate_image(value)
        return value

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ):
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as error:
            raise RequestValidationError(error.errors()) from error


class ProfileResponseSchema(BaseUserProfileSchema):
    id: int
    user_id: int
    avatar: HttpUrl
