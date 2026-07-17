from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[UploadFile] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_(cls, v):
        if v:
            validate_name(v)
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender_(cls, v):
        if v:
            validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date_(cls, v):
        if v:
            validate_birth_date(v)
        return v

    @field_validator("avatar")
    @classmethod
    def validate_avatar_(cls, v):
        if v:
            validate_image(v)
        return v

    @classmethod
    def as_form(
        cls,
        first_name: Optional[str] = Form(None),
        last_name: Optional[str] = Form(None),
        gender: Optional[str] = Form(None),
        date_of_birth: Optional[str] = Form(None),
        info: Optional[str] = Form(None),
        avatar: Optional[UploadFile] = File(None)
    ):
        parsed_date = date.fromisoformat(date_of_birth) if date_of_birth else None
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=parsed_date,
            info=info,
            avatar=avatar
        )


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    class Config:
        from_attributes = True
