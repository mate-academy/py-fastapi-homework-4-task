import datetime

from fastapi import UploadFile
from pydantic import ConfigDict, BaseModel, field_validator, HttpUrl

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
    validate_image,
)


class UserProfileBaseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: datetime.date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    def name_validator(cls, value):
        validate_name(value)
        return value.lower()

    @field_validator("gender")
    def gender_validator(cls, value):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    def date_of_birth_validator(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("info")
    def info_validator(cls, value):
        if not value.strip():
            raise ValueError(
                "The info field must not be empty or consist only of spaces."
            )
        return value

    @field_validator("avatar")
    def avatar_validator(cls, value):
        validate_image(value)
        return value


class UserProfileResponseSchema(UserProfileBaseSchema):
    id: int
    avatar: HttpUrl

    model_config = ConfigDict(from_attributes=True)
