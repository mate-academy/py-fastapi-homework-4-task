from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional, Any

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)


class ProfileCreateValidationModel(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: Optional[str] = None

    @classmethod
    @field_validator('first_name')
    def check_first_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @classmethod
    @field_validator('last_name')
    def check_last_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @classmethod
    @field_validator('gender')
    def check_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @classmethod
    @field_validator('date_of_birth', mode='before')
    def check_age(cls, value: Any) -> date:
        if isinstance(value, str):
            parsed_date = date.fromisoformat(value)
            validate_birth_date(parsed_date)
            return parsed_date
        elif isinstance(value, date):
            validate_birth_date(value)
            return value
        return value

    @classmethod
    @field_validator('info')
    def check_info(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and (value == "" or value.isspace()):
            raise ValueError("Info cannot be empty or consist only of spaces.")
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

    class Config:
        from_attributes = True
