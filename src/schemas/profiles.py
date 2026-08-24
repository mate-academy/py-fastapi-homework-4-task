from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# Reusing your project's custom validation functions
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50, description="User's legal given name")
    last_name: str = Field(..., min_length=2, max_length=50, description="User's legal family surname")
    birth_date: Optional[date] = Field(None, alias="date_of_birth", description="ISO Date format YYYY-MM-DD")
    gender: Optional[str] = Field(None, description="Gender description matching system constraints")
    info: Optional[str] = Field(None, description="Detailed profile summary notes text")

    @field_validator("first_name")
    @classmethod
    def check_first_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("last_name")
    @classmethod
    def check_last_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("birth_date")
    @classmethod
    def check_birth_date(cls, value: Optional[date]) -> Optional[date]:
        if value is not None:
            validate_birth_date(value)
        return value

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            validate_gender(value)
        return value


class ProfileCreate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    id: int
    user_id: int
    avatar: Optional[str] = Field(None, description="Public S3 bucket target location link string")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def handle_attribute_fallbacks(cls, data: any) -> any:
        """
        Interceptive fallback mapper ensuring cross-compatibility between database naming mappings
        and presentation layout serialization definitions.
        """
        if not isinstance(data, dict):
            # Mirror model attributes smoothly before conversion engine initialization
            if hasattr(data, "avatar_url") and getattr(data, "avatar", None) is None:
                setattr(data, "avatar", getattr(data, "avatar_url"))
            elif hasattr(data, "avatar") and getattr(data, "avatar_url", None) is None:
                setattr(data, "avatar_url", getattr(data, "avatar"))
        return data
