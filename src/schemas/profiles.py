from datetime import date
from enum import Enum as PyEnum

from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
)
from database.models.accounts import GenderEnum


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    def validate_names(cls, v: str) -> str:
        validate_name(v)
        return v.lower()

    @field_validator("gender")
    def validate_gender_field(cls, v: GenderEnum) -> GenderEnum:
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    def validate_birth(cls, v: date) -> date:
        validate_birth_date(v)
        return v

    @field_validator("info")
    def validate_info(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Info cannot be empty.")
        return v


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
