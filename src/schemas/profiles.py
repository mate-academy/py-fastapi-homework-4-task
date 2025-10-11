from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, field_validator

from database.models.accounts import GenderEnum
from validation import (validate_birth_date, validate_gender, validate_image,
                        validate_info, validate_name)


class ProfileCreateRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_last_name(cls, value):
        validate_name(value)
        return value.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        validate_image(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        validate_info(value)
        return value


class ProfileCreateResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    avatar: str
    gender: str
    date_of_birth: date
    info: str
