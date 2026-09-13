from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileModel(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str | None
    avatar: UploadFile

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        return validate_name(value)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value):
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value):
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, value):
        return validate_birth_date(value)

    @field_validator("avatar")
    @classmethod
    def validate_image_field(cls, value):
        return validate_image(value)

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
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
            error = e.errors()[0]

            raise HTTPException(
                status_code=422,
                detail=error["msg"],
            )
