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
    def validate_date_of_birth(cls, value: str) -> date:
        return validate_birth_date(value)

    @field_validator("avatar")
    def validate_avatar(cls, value: str) -> bytes:
        return validate_image(value)


class ProfileResponseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar_url: Optional[str]
