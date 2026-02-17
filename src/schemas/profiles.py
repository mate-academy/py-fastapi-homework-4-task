from datetime import date

from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

# Write your code here
class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[UploadFile] = None


    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        validate_name(v)
        return v

    # -------- GENDER --------
    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, v: str) -> str:
        validate_gender(v)
        return v

    # -------- DOB --------
    @field_validator("date_of_birth")
    @classmethod
    def validate_birth(cls, v: date) -> date:
        validate_birth_date(v)
        return v

    # -------- INFO --------
    @field_validator("info")
    @classmethod
    def validate_info(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Info cannot be empty.")
        return v.strip()


    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v) -> str:
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

    model_config = {"from_attributes": True}
