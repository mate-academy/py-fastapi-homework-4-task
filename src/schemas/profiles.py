from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, Field

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: Optional[str] = Field(None)
    last_name: Optional[str] = Field(None)
    gender: Optional[str] = Field(None)
    date_of_birth: Optional[date] = Field(None)
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_first_name(cls, value: str) -> Optional[str]:
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> Optional[str]:
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> Optional[date]:
        return validate_birth_date(value)

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> Optional[str]:
        if value is None or value.strip() == "":
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[date]
    info: str
    avatar: Optional[str]

    class Config:
        from_attributes = True
