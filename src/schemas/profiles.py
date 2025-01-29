from datetime import date

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator, ValidationError

from validation import validate_name, validate_gender, validate_birth_date, validate_image


class ProfileRequestForm(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...)
    ):
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        validate_name(value)
        return value

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value):
        validate_name(value)
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        validate_image(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        if not value or not value.strip():
            raise ValidationError("info cannot be empty")
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
