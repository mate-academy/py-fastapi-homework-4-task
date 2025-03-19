from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class UserProfileSchema(BaseModel):
    first_name: str = Field(..., description="Must contain only English letters.")
    last_name: str = Field(..., description="Must contain only English letters.")
    gender: str = Field(..., description="Must be a valid gender option.")
    date_of_birth: str = Field(..., description="Must be a valid date and user must be at least 18 years old.")
    info: str = Field(..., description="Cannot be empty or consist only of spaces.")
    avatar: UploadFile = Field(..., description="Must be a valid image file (JPG, JPEG, PNG) and not exceed 1MB.")

    @validator("first_name", "last_name")
    def validate_names(cls, value):
        if not validate_name(value):
            raise ValueError("Name must contain only English letters.")
        return value

    @validator("gender")
    def validate_gender_option(cls, value):
        if not validate_gender(value):
            raise ValueError("Invalid gender option.")
        return value

    @validator("date_of_birth")
    def validate_dob(cls, value):
        if not validate_birth_date(value):
            raise ValueError("Invalid date or user must be at least 18 years old.")
        return value

    @validator("info")
    def validate_info(cls, value):
        if not value.strip():
            raise ValueError("Info cannot be empty or contain only spaces.")
        return value

    @validator("avatar")
    def validate_avatar(cls, value):
        if not validate_image(value):
            raise ValueError("Invalid image file. Must be JPG, JPEG, or PNG and not exceed 1MB.")
        return value
