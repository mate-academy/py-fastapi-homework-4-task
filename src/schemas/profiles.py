import datetime
from typing import Annotated

from fastapi import UploadFile, Form, File
from pydantic import (
    BaseModel,
    field_validator,
    HttpUrl,
    Field,
    AfterValidator,
    ConfigDict,
    BeforeValidator
)

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


def check_name(value: str) -> str:
    validate_name(value)
    return value.lower()


def check_gender(value: str) -> str:
    validate_gender(value)
    return value


def check_birth_date(value: datetime.date) -> datetime.date:
    validate_birth_date(value)
    return value


def check_image(value: UploadFile) -> UploadFile:
    validate_image(value)
    return value


Name = Annotated[str, Field(max_length=100), AfterValidator(check_name)]
Gender = Annotated[GenderEnum, BeforeValidator(check_gender)]
BirthDate = Annotated[datetime.date, AfterValidator(check_birth_date)]
Image = Annotated[UploadFile, AfterValidator(check_image)]


class ProfileRequestSchema(BaseModel):
    first_name: Annotated[Name, Form()]
    last_name: Annotated[Name, Form()]
    gender: Annotated[Gender, Form()]
    date_of_birth: Annotated[BirthDate, Form()]
    info: Annotated[str, Form()]
    avatar: Annotated[Image, File()]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: datetime.date
    info: str
    avatar: HttpUrl

    model_config = ConfigDict(from_attributes=True)
