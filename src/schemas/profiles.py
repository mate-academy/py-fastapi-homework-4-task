from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from src.validation.profile import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileRequestSchema(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    birth_date: Optional[date]
    info: Optional[str]
    avatar: UploadFile = File(...),

    @field_validator("first_name", "last_name")
    @classmethod
    def _validate_name(cls, v: str):
        return validate_name(v)

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, v: str):
        return validate_gender(v)

    @field_validator("birth_date")
    @classmethod
    def _validate_birth_date(cls, v: date):
        return validate_birth_date(v)

    @field_validator("avatar")
    @classmethod
    def _validate_image(cls, v: str | None):
        if v is None:
            return v
        return validate_image(v)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
