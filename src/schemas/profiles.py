from __future__ import annotations
from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileRequestFormSchema(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[date]
    info: Optional[str]
    avatar: Optional[UploadFile]

    @field_validator("first_name", mode="before")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("last_name", mode="before")
    @classmethod
    def validate_last_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth", mode="after")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
        return value

    @classmethod
    def as_form(
        cls,
        first_name: Optional[str] = Form(),
        last_name: Optional[str] = Form(),
        gender: Optional[str] = Form(),
        date_of_birth: Optional[date] = Form(),
        info: Optional[str] = Form(),
        avatar: Optional[UploadFile] = File(),
    ) -> ProfileRequestFormSchema:
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )


class UserProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: str
    info: str
    avatar: HttpUrl
