from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    gender: str
    date_of_birth: datetime.date
    info: str = Field(..., min_length=1, max_length=2000)
    avatar: bytes

    @field_validator("first_name")
    @classmethod
    def first_name_valid(cls, v: str) -> str:
        validate_name(v)
        return v.strip().lower()

    @field_validator("last_name")
    @classmethod
    def last_name_valid(cls, v: str) -> str:
        validate_name(v)
        return v.strip().lower()

    @field_validator("gender")
    @classmethod
    def gender_valid(cls, v: str) -> str:
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_valid(cls, v: datetime.date) -> datetime.date:
        validate_birth_date(v)
        return v

    @field_validator("info")
    @classmethod
    def info_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Invalid input data.")
        return v.strip()

    @field_validator("avatar")
    @classmethod
    def avatar_valid(cls, v: bytes) -> bytes:
        validate_image(v)
        return v


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: datetime.date
    info: str
    avatar: Optional[str] = None

    class Config:
        orm_mode = True
