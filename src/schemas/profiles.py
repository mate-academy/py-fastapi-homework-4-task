from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[bytes] = None

    @field_validator("first_name", "last_name")
    def validate_names(cls, value):
        return validate_name(value)

    @field_validator("gender")
    def validate_gender_field(cls, value):
        return validate_gender(value)

    @field_validator("date_of_birth")
    def validate_birth_date_field(cls, value):
        return validate_birth_date(value)

    @field_validator("info")
    def validate_info(cls, value):
        if not value.strip():
            raise ValueError("Info cannot be empty or contain only spaces.")
        return value

    @field_validator("avatar")
    def validate_avatar(cls, value):
        return validate_image(value)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
