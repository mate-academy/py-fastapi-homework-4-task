from datetime import date
from enum import Enum
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, field_validator, ConfigDict

# Імпортуємо функції валідації напряму з модуля, щоб уникнути циклічних імпортів
from validation.profile import validate_english_letters, validate_age, validate_info, validate_image


class GenderEnum(str, Enum):
    MALE = "man"
    FEMALE = "woman"


class ProfileCreateRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('first_name', 'last_name')
    @classmethod
    def check_names(cls, v: str) -> str:
        return validate_english_letters(v)

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: str) -> str:
        allowed = [e.value for e in GenderEnum]
        if v not in allowed:
            raise ValueError(f"Gender must be one of {allowed}")
        return v

    @field_validator('date_of_birth')
    @classmethod
    def check_age(cls, v: date) -> date:
        return validate_age(v)

    @field_validator('info')
    @classmethod
    def check_info(cls, v: str) -> str:
        return validate_info(v)

    @field_validator('avatar')
    @classmethod
    def check_avatar(cls, v: UploadFile) -> UploadFile:
        return validate_image(v)


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: Optional[str] = None
    user_id: int

    model_config = ConfigDict(from_attributes=True)
