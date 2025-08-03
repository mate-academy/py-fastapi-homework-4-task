from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileBaseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile
    
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
    
    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v):
        return validate_image(v)

class ProfileRequestSchema(ProfileBaseSchema):
    pass

class ProfileResponseSchema(ProfileBaseSchema):
    id: int
    user_id: int
    avatar: HttpUrl
    model_config = {"from_attributes": True}