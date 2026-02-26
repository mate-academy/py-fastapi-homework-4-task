from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)

class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def chek_name(cls, v: str):
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


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[HttpUrl] = None

    model_config = ConfigDict(from_attributes=True)
