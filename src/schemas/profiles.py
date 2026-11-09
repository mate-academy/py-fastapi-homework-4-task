from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


def _check(validator, value):
    try:
        validator(value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return value


class ProfileCreateRequestSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

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
        info: str = Form(""),
        avatar: UploadFile = File(...),
    ):
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )

    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, value):
        return _check(validate_name, value).lower()

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value):
        return _check(validate_gender, value)

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value):
        return _check(validate_birth_date, value)

    @field_validator("info")
    @classmethod
    def check_info(cls, value):
        if not value.strip():
            raise HTTPException(
                status_code=422,
                detail="Info field cannot be empty or contain only spaces."
            )
        return value

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value):
        return _check(validate_image, value)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl
