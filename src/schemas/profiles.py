from datetime import date
from typing import Optional, Any

from pydantic import BaseModel, field_validator, ConfigDict

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
    validate_image
)

class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Any

    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, v: str):
        validate_name(v)
        return v

    @field_validator("gender")
    @classmethod
    def check_gender(cls, v: str):
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, v: date):
        validate_birth_date(v)
        return v


    @field_validator("info")
    @classmethod
    def check_info(cls, v: str):
        if not v or v.isspace():
            raise ValueError("Info cannot be empty or consist only of spaces.")
        return v

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, v: Any):
        if v:
            validate_image(v)
        return v

class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[str]

    model_config = ConfigDict(from_attributes=True)
