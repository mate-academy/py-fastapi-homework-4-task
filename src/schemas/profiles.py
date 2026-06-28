from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator, ConfigDict
from database.models.accounts import GenderEnum

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str

    @field_validator("first_name")
    @classmethod
    def check_first_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("last_name")
    @classmethod
    def check_last_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str) -> str:
        if not value or value.isspace():
            raise ValueError("Info cannot be empty or consist only of spaces.")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[str] = None
