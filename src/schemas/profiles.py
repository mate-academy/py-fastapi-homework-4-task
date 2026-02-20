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
        model_config = {"from_attributes": True}
