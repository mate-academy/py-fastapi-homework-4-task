from datetime import date
from typing import Annotated

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import (
    BaseModel,
    field_validator,
    HttpUrl,
    AfterValidator,
    StringConstraints,
    ConfigDict,
)

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: Annotated[GenderEnum, AfterValidator(validate_gender)]
    date_of_birth: Annotated[date, AfterValidator(validate_birth_date)]
    info: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    avatar: Annotated[UploadFile, AfterValidator(validate_image)]

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        validate_name(value)
        return value


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: HttpUrl
