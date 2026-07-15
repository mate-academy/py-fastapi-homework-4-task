from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)

# Write your code here


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name")
    @classmethod
    def check_first_name(cls, value: str) -> str:
        # Убираем лишние пробелы и переводим в нижний регистр, как в примере ответа
        cleaned = value.strip().lower()
        validate_name(cleaned)
        return cleaned

    @field_validator("last_name")
    @classmethod
    def check_last_name(cls, value: str) -> str:
        cleaned = value.strip().lower()
        validate_name(cleaned)
        return cleaned

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: str) -> str:
        cleaned = value.strip().lower()
        validate_gender(cleaned)
        return cleaned

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Info cannot be empty or consist only of spaces.")
        return value.strip()


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
    model_config = {"from_attributes": True}
