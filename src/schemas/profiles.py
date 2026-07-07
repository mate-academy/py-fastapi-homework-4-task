from datetime import date

from fastapi import UploadFile, Form, File
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class BaseProfileSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

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
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        if hasattr(value, "file"):
            validate_image(value)
        return value


class ProfileCreateSchema(BaseProfileSchema):
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
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc


class ProfileDetailSchema(BaseProfileSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    avatar: str
    user_id: int
