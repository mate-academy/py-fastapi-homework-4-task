from __future__ import annotations
from datetime import date


from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

# src/schemas/profiles.py


from datetime import date
from pydantic import BaseModel, Field, field_validator


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(..., description="Only English letters")
    last_name: str = Field(..., description="Only English letters")
    gender: str = Field(..., description="Allowed values defined by GenderEnum")
    date_of_birth: date = Field(..., description="YYYY-MM-DD; age >= 18")
    info: str = Field(..., min_length=1, description="Non-empty bio/about")

    @field_validator("first_name")
    @classmethod
    def _validate_first_name(cls, v: str) -> str:
        validate_name(v)  # має кинути ValueError/ValidationError при невдачі
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
        # має перевірити формат і >= 18 років
        validate_birth_date(v)
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

    class Config:
        from_attributes = True  # для ORM mode


# Хелпер для валідації зображення (UploadFile читаємо в роуті і прокидуємо сюди)
def validate_avatar_bytes(filename: str, content_type: str | None, data: bytes) -> None:
    """
    Використовуємо штатну валідацію з validation.validate_image:
    - дозволені: jpg, jpeg, png
    - розмір <= 1MB
    """
    # many validators очікують filename+content_type+bytes (або subset) — тримаємо універсально
    validate_image(filename, content_type, data, max_size_mb=1)
