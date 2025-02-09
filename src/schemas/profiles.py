import datetime
from typing import Any

from fastapi import UploadFile, Form, File
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator, ValidationError

from validation import validate_name, validate_gender, validate_birth_date


class ProfileRequestForm(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: datetime.date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: datetime.date = Form(),
        info: str = Form(),
        avatar: UploadFile = File(),
    ) -> Any:
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as exc:
            errors = exc.errors()
            for error in errors:
                if "input" in error:
                    error.pop("input")
            raise RequestValidationError(errors)

    @field_validator("first_name")
    def validate_first_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("last_name")
    def validate_last_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("gender")
    def validate_gender_field(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    def validate_birth_date_field(cls, value: datetime.date) -> datetime.date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    def validate_info(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("avatar")
    def validate_avatar_field(cls, value: UploadFile) -> UploadFile:
        allowed_types = ["image/jpeg", "image/png"]
        if value.content_type not in allowed_types:
            raise ValueError("Invalid image format")
        value.file.seek(0, 2)
        size = value.file.tell()
        if size > 1 * 1024 * 1024:
            raise ValueError("Image size exceeds 1 MB")
        value.file.seek(0)
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: datetime.date
    info: str
    avatar: str

    model_config = {"from_attributes": True}
