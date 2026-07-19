from datetime import date

from pydantic import ValidationError
from fastapi.exceptions import RequestValidationError
from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator, HttpUrl

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)


class UserProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ):
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as e:
            raise RequestValidationError(e.errors())

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str):
        return validate_name(value)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value: str):
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value):
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date_field(cls, value):
        return validate_birth_date(value)

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str):
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value


class UserProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    avatar: HttpUrl | None = None
    gender: GenderEnum
    date_of_birth: date
    info: str

    model_config = {
        "from_attributes": True
    }
