from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator
from src.validation import validate_name, validate_gender, validate_birth_date


class UserProfileCreateSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def validate_names(cls, v):
        if v is None:
            return v
        validate_name(v)
        return v.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender_field(cls, v):
        if v is None:
            return v
        validate_gender(v)
        return v

    @field_validator("date_of_birth", mode="after")
    @classmethod
    def validate_birth(cls, v):
        if v is None:
            return v
        validate_birth_date(v)  # валідація кидає ValueError
        return v

    @field_validator("info", mode="before")
    @classmethod
    def validate_info(cls, v):
        if v is None:
            return v
        if v.strip() == "":
            # тести очікують саме цей текст
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v


class UserProfileResponseSchema(UserProfileCreateSchema):
    id: int
    avatar: str
