import re
from datetime import date
from enum import Enum
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, field_validator, ConfigDict

# Налаштування для файлів
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB
# ВАЖЛИВО: GIF тут НЕМАЄ, щоб тест на invalid format спрацював і повернув 422
ALLOWED_TYPES = ["image/jpeg", "image/jpg", "image/png"]


class GenderEnum(str, Enum):
    MALE = "man"
    FEMALE = "woman"


class ProfileCreateRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str  # str для кастомної валідації тексту помилки
    date_of_birth: date
    info: str
    avatar: UploadFile

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_english_letters(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z]+$", v):
            raise ValueError(f"{v} contains non-english letters")
        return v

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: str) -> str:
        allowed = [e.value for e in GenderEnum]
        if v not in allowed:
            # Текст підігнаний під тест: "Gender must be one of ['man', 'woman']"
            raise ValueError(f"Gender must be one of {allowed}")
        return v

    @field_validator('date_of_birth')
    @classmethod
    def validate_age(cls, v: date) -> date:
        if v.year <= 1900:
            raise ValueError("Invalid birth date - year must be greater than 1900.")

        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))

        if age < 18:
            raise ValueError("You must be at least 18 years old to register.")
        return v

    @field_validator('info')
    @classmethod
    def validate_info(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @field_validator('avatar')
    @classmethod
    def validate_avatar(cls, v: UploadFile) -> UploadFile:
        if v.content_type not in ALLOWED_TYPES:
            raise ValueError("Invalid image format")

        v.file.seek(0, 2)
        file_size = v.file.tell()
        v.file.seek(0)

        if file_size > MAX_FILE_SIZE:
            raise ValueError("Image size exceeds 1 MB")

        return v


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