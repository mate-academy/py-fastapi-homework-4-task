from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)

# Write your code here

class UserProfileBase(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        validate_name(value)
        return value

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value):
        validate_name(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str):
        if not len(value.strip()) > 0:
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        return value.strip()

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str):
        validate_gender(value)
        return value


class CreateUserProfileRequest(UserProfileBase):
    avatar: UploadFile

    @field_validator("avatar", mode="after")
    @classmethod
    def validate_avatar(cls, value: UploadFile):
        validate_image(value)
        return value


class CreateUserProfileResponse(UserProfileBase):
    id: int
    avatar: str
