from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, HttpUrl, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileFormData(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    def validate_first_name(cls, value):
        try:
            validate_name(value)
        except ValueError as e:
            raise ValueError(f"First name error: {str(e)}")
        return value.lower()

    @field_validator("last_name")
    def validate_last_name(cls, value):
        try:
            validate_name(value)
        except ValueError as e:
            raise ValueError(f"Last name error: {str(e)}")
        return value.lower()

    @field_validator("gender")
    def validate_gender_field(cls, value):
        try:
            validate_gender(value)
        except ValueError as e:
            raise ValueError(f"Gender error: {str(e)}")
        return value

    @field_validator("date_of_birth")
    def validate_birth_date_field(cls, value):
        try:
            validate_birth_date(value)
        except ValueError as e:
            raise ValueError(f"Birth date error: {str(e)}")
        return value

    @field_validator("info")
    def check_info(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("avatar")
    def validate_avatar(cls, value):
        try:
            validate_image(value)
        except ValueError as e:
            raise ValueError(f"Avatar error: {str(e)}")
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl

    model_config = {"from_attributes": True}
