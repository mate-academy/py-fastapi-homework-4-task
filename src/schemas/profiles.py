from datetime import date
from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
)


class ProfileCreateRequest(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def check_names(cls, name: str) -> str:
        try:
            validate_name(name)
        except ValueError as e:
            raise ValueError(str(e))
        return name

    @field_validator("gender")
    @classmethod
    def check_gender(cls, v: str) -> str:
        try:
            validate_gender(v)
        except ValueError as e:
            raise ValueError(str(e))
        return v

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, v: date) -> date:
        try:
            validate_birth_date(v)
        except ValueError as e:
            raise ValueError(str(e))
        return v

    @field_validator("info")
    @classmethod
    def check_info(cls, info: str) -> str:
        if not info or not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        if not info or info.isspace():
            raise ValueError("Info field cannot be empty")
        return info


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
