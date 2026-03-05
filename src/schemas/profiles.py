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
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl


class ProfileRequestSchema(BaseModel):
    first_name: str = Form(...)
    last_name: str = Form(...)
    gender: str = Form(...)
    date_of_birth: date = Form(...)
    info: str = Form(...)
    avatar: UploadFile = File(...)

    @field_validator("first_name")
    def validate_first_name(cls, value):
        if value is not None:
            validate_name(value)
        return value

    @field_validator("last_name")
    def validate_last_name(cls, value):
        if value is not None:
            validate_name(value)
        return value

    @field_validator("gender")
    def validate_gender_field(cls, value):
        if value is not None:
            validate_gender(value)
        return value

    @field_validator("date_of_birth")
    def validate_date_of_birth_field(cls, value):
        if value is not None:
            validate_birth_date(value)
        return value

    @field_validator("info")
    def validate_info(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Info cannot be empty or whitespace only.")
        return value

    @field_validator("avatar")
    def validate_avatar(cls, value):
        if value is not None:
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
    ) -> "ProfileRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )
