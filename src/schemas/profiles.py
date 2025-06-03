from datetime import date
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, Field, field_validator, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileBase(BaseModel):
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    gender: str = Field(..., description="User's gender")
    date_of_birth: date = Field(..., description="User's date of birth")
    info: str = Field(..., description="User's profile information")

    @field_validator('first_name')
    @classmethod
    def validate_first_name(cls, v):
        validate_name(v)
        return v

    @field_validator('last_name')
    @classmethod
    def validate_last_name(cls, v):
        validate_name(v)
        return v

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v):
        validate_gender(v)
        return v

    @field_validator('date_of_birth')
    @classmethod
    def validate_date_of_birth(cls, v):
        validate_birth_date(v)
        return v

    @field_validator('info')
    @classmethod
    def validate_info(cls, v):
        if not v or not v.strip():
            raise ValueError("Info cannot be empty or consist only of spaces")
        return v


class ProfileCreate(ProfileBase):
    avatar: Optional[UploadFile] = Field(None, description="User's avatar image")

    @field_validator('avatar')
    @classmethod
    def validate_avatar(cls, v):
        if v is not None:
            validate_image(v)
        return v


class ProfileResponse(ProfileBase):
    id: int = Field(..., description="Profile ID")
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar")
    model_config = ConfigDict(from_attributes=True)
