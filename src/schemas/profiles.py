from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl


class ProfileCreate(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile | None = None

    @field_validator("first_name")
    def validate_first_name(cls, v: str) -> str:
        validate_name(v)
        return v.lower()

    @field_validator("last_name")
    def validate_last_name(cls, v: str) -> str:
        validate_name(v)
        return v.lower()

    @field_validator("gender")
    def validate_gender_field(cls, v: str) -> str:
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    def validate_birth_date_field(cls, v: date) -> date:
        validate_birth_date(v)
        return v

    @field_validator("info")
    def validate_info(cls, v: str) -> str:
        if v is None or not v.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @field_validator("avatar")
    def validate_avatar(cls, v: UploadFile | None) -> UploadFile | None:
        if v is not None:
            validate_image(v)
        return v
