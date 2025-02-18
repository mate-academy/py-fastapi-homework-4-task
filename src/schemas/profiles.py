from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date
from validation import validate_name, validate_image, validate_gender, validate_birth_date


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(..., example="John")
    last_name: str = Field(..., example="Doe")
    gender: str = Field(..., example="man")
    date_of_birth: date = Field(..., example="1990-01-01")
    info: str = Field(..., example="This is a test profile.")
    avatar: Optional[bytes] = Field(None, example="<binary-image-data>")

    @validator('first_name', 'last_name')
    def validate_names(cls, value):
        return validate_name(value)

    @validator('gender')
    def validate_gender(cls, value):
        return validate_gender(value)

    @validator('date_of_birth')
    def validate_birth_date(cls, value):
        return validate_birth_date(value)

    @validator('info')
    def validate_info(cls, value):
        if not value.strip():
            raise ValueError("Info cannot be empty or consist only of spaces.")
        return value

    @validator('avatar')
    def validate_avatar(cls, value):
        return validate_image(value)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
