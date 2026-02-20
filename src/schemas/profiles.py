from datetime import date

from fastapi import Form
from pydantic import BaseModel, ConfigDict, field_validator

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)

class ProfileResponseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
    model_config = ConfigDict(from_attributes=True)

class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    
    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v):
        return validate_name(v)
    
    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v):
        return validate_name(v)
    
    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        return validate_gender(v)
    
    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v):
        return validate_birth_date(v)


async def get_profile_form(
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
) -> ProfileRequestSchema:
    
    return ProfileRequestSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
    )