from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)
from database.models.accounts import GenderEnum


# Write your code here
class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def check_english_letter(cls, value: str):
        validate_name(name=value)
        return value.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def choosing_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def info_validation(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return stripped_value

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
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

    model_config = {
        "from_attributes": True
    }
