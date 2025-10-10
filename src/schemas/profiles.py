from datetime import date

from pydantic import BaseModel, Field, field_validator

from validation.profile import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):

    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    gender: str = Field(..., description="User's gender")
    date_of_birth: date = Field(..., description="User's date of birth")
    info: str = Field(..., description="Additional information about the user")
    avatar: str = Field(..., description="Base64 encoded avatar image")

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        return validate_name(value, "First name")

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value: str) -> str:
        return validate_name(value, "Last name")

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, value: date) -> date:
        return validate_birth_date(value)

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Info cannot be empty or contain only spaces")
        return value.strip()

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, value: str) -> str:
        """Validate avatar is a valid image format and size."""
        return validate_image(value)


class ProfileResponseSchema(BaseModel):
    """Schema for profile response."""

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    class Config:
        from_attributes = True
