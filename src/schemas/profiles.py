from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field, field_validator

# Валідації з пакету validation (умова задачі)
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(..., description="Only English letters")
    last_name: str = Field(..., description="Only English letters")
    gender: str = Field(..., description="Allowed values defined by GenderEnum")
    date_of_birth: date = Field(..., description="YYYY-MM-DD; age >= 18")
    info: str = Field(..., min_length=1, description="Non-empty bio/about")

    @field_validator("first_name")
    @classmethod
    def _validate_first_name(cls, v: str) -> str:
        validate_name(v)
        return v

    @field_validator("last_name")
    @classmethod
    def _validate_last_name(cls, v: str) -> str:
        validate_name(v)
        return v

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, v: str) -> str:
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _validate_birth_date(cls, v: date) -> date:
        validate_birth_date(v)  # має перевіряти вік >= 18
        return v

    @field_validator("info")
    @classmethod
    def _validate_info(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Info must not be empty.")
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

    # Pydantic v2
    model_config = {"from_attributes": True}


def validate_avatar_bytes(filename: str, content_type: str | None, data: bytes) -> None:
    """
    Обгортка над validation.validate_image з сумісністю зі старими/новими сигнатурами.
    Дозволені: JPG/JPEG/PNG; розмір <= 1MB.
    """
    try:
        # новіша сигнатура (з max_size_mb)
        validate_image(filename, content_type, data, max_size_mb=1)
        return
    except TypeError:
        # старіша сигнатура — перевіримо розмір самі
        if len(data) > 1 * 1024 * 1024:
            raise ValueError("Image size must be <= 1MB.")
        validate_image(filename, content_type, data)
