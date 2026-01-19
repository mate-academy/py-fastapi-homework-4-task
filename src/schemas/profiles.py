import imghdr
import re
from datetime import date, timedelta
from typing import Optional

from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

# Write your code here
class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[bytes]

    @field_validator("first_name", "last_name")
    def validate_names(cls, value: str) -> str:
        return validate_name(value)

    @field_validator("gender")
    def validate_gender(cls, value: str) -> str:
        return validate_gender(value)

    @field_validator("date_of_birth")
    def validate_date_of_birth(cls, value: date) -> date:
        return validate_birth_date(value)

    @field_validator("avatar")
    def validate_avatar(cls, value: Optional[bytes]) -> bytes:
        return validate_image(value)

    @field_validator("info")
    def validate_info(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Info cannot be empty or only spaces.")
        return value


class ProfileResponseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar_url: Optional[str]
