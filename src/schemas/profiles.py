from datetime import date
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
)


class UserProfileSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: Optional[str] = None
    avatar: Optional[HttpUrl] = None

    model_config = {"from_attributes": True}

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date_field(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        return value
