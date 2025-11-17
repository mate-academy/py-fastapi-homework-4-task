from datetime import date
from enum import Enum as PyEnum

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileRequestSchema(BaseModel):
    first_name: str = Form(...)
    last_name: str = Form(...)
    gender: str = Form(...)
    date_of_birth: date = Form(...)
    info: str = Form(...)
    avatar: UploadFile = File(...)

    @field_validator("first_name", "last_name")
    def validate_names(cls, v: str) -> str:
        name = validate_name(v)
        return name.lower()

    @field_validator("gender")
    def validate_gender_field(cls, v: str) -> str:
        gender = validate_gender(v)
        if isinstance(gender, PyEnum):
            return str(gender.value).lower()
        return str(gender).lower()

    @field_validator("date_of_birth")
    def validate_birth(cls, v: date) -> date:
        return validate_birth_date(v)

    @field_validator("info")
    def validate_info(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Info cannot be empty.")
        return v

    @field_validator("avatar")
    def validate_avatar(cls, v: UploadFile) -> UploadFile:
        return validate_image(v)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    @field_validator("first_name", "last_name")
    def normalize_names(cls, v: str) -> str:
        return str(v).lower()

    @field_validator("gender")
    def normalize_gender(cls, v):
        if isinstance(v, PyEnum):
            return str(v.value).lower()

        if isinstance(v, str):
            if "." in v:
                return v.split(".")[-1].lower()
            return v.lower()

        return str(v).lower()

    model_config = {"from_attributes": True}
