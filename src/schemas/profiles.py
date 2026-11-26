from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, HttpUrl, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date, validate_info
)


def _validation_error(error: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        try:
            validate_name(value)
        except ValueError as error:
            raise _validation_error(error)
        return value.lower()

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: str) -> str:
        try:
            validate_gender(value)
        except ValueError as error:
            raise _validation_error(error)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date) -> date:
        try:
            validate_birth_date(value)
        except ValueError as error:
            raise _validation_error(error)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str) -> str:
        if not value.strip():
            raise _validation_error(ValueError("Info field cannot be empty or contain only spaces."))
        return value

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value: UploadFile) -> UploadFile:
        try:
            validate_image(value)
        except ValueError as error:
            raise _validation_error(error)
        return value

    @classmethod
    def as_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(""),
            avatar: UploadFile = File(...),
    ) -> "ProfileCreateSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True
    }
