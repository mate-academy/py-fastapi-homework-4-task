from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, field_validator, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    def validate_first_name(cls, value: str):
        validate_name(value)
        value = value.lower()
        return value

    @field_validator("last_name")
    def validate_last_name(cls, value: str):
        validate_name(value)
        value = value.lower()
        return value

    @field_validator("gender")
    def validate_gender(cls, value: str):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    def validate_date_of_birth(cls, value: date):
        validate_birth_date(value)
        return value

    @field_validator("info")
    def validate_info(cls, value: str):
        if value.strip() == "":
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        return value

    @field_validator("avatar")
    def validate_avatar(cls, value: UploadFile):
        validate_image(value)
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = ConfigDict(from_attributes=True)
