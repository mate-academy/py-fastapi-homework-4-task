from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional
from database.models.accounts import GenderEnum
from validation.profile import validate_name, validate_gender, validate_birth_date, validate_image


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None
    avatar: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def check_names(cls, v):
        return validate_name(v)

    @field_validator("gender")
    @classmethod
    def check_gender(cls, v):
        return validate_gender(v)

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, v):
        return validate_birth_date(v)

    @field_validator("date_of_birth")
    @classmethod
    def check_image(cls, v):
        return validate_image(v)

    @field_validator("info")
    @classmethod
    def check_info(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Info cannot be empty or just whitespace")
        return v


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: Optional[str]
    last_name: Optional[str]
    avatar: Optional[str]
    gender: Optional[GenderEnum]
    date_of_birth: Optional[date]
    info: Optional[str]
    user_id: int

    class Config:
        from_attributes = True
