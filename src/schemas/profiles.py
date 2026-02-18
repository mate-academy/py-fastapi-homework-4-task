from datetime import date

from pydantic import BaseModel, validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)
from typing import Optional

class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @validator('first_name')
    def check_first_name(cls, v):
        if not validate_name(v):
            raise ValueError("Invalid first name. Only English letters are allowed.")
        return v

    @validator('last_name')
    def check_last_name(cls, v):
        if not validate_name(v):
            raise ValueError("Invalid last name. Only English letters are allowed.")
        return v

    @validator('gender')
    def check_gender(cls, v):
        if not validate_gender(v):
            raise ValueError("Invalid gender value.")
        return v

    @validator('date_of_birth')
    def check_dob(cls, v):
        if not validate_birth_date(v):
            raise ValueError("Invalid date of birth or user is under 18 years old.")
        return v

    @validator('info')
    def check_info(cls, v):
        if not v or v.strip() == '':
            raise ValueError("Info cannot be empty or whitespace only.")
        return v

class ProfileResponseSchema(ProfileRequestSchema):
    id: int
    user_id: int
    avatar: Optional[str]

    class Config:
        orm_mode = True
