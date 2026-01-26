from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator, ValidationError
from fastapi import HTTPException, status

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    """
    Schema for creating a user profile with validation.

    This schema handles the validation of user profile data including
    first name, last name, gender, date of birth, and additional info.
    The avatar image is handled separately as UploadFile.
    """
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    model_config = {
        "from_attributes": True
    }

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        """
        Validate first name using the validation module.
        Must contain only English letters.
        """
        try:
            validate_name(value)
        except ValueError as e:
            raise ValueError(str(e))
        return value.lower()

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value: str) -> str:
        """
        Validate last name using the validation module.
        Must contain only English letters.
        """
        try:
            validate_name(value)
        except ValueError as e:
            raise ValueError(str(e))
        return value.lower()

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        """
        Validate gender using the validation module.
        Must be a valid gender option.
        """
        try:
            validate_gender(value)
        except ValueError as e:
            raise ValueError(str(e))
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, value: date) -> date:
        """
        Validate date of birth using the validation module.
        User must be at least 18 years old.
        """
        try:
            validate_birth_date(value)
        except ValueError as e:
            raise ValueError(str(e))
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        """
        Validate info field.
        Cannot be empty or consist only of whitespace.
        """
        if not value or not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value.strip()


class ProfileResponseSchema(BaseModel):
    """
    Schema for profile response.

    Returns the complete profile information including the avatar URL.
    """
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True
    }
