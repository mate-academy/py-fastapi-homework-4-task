from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    @classmethod
    def check_first_name(cls, value):
        validate_name(value)
        return value

    @field_validator("last_name")
    @classmethod
    def check_last_name(cls, value):
        validate_name(value)
        return value

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_date_of_birth(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value):
        validate_info(value)
        return value

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value):
        validate_image(value)
        return value

    @classmethod
    def from_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...)
    ):
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=[
                    {"loc": err["loc"], "msg": err["msg"], "type": err["type"]}
                    for err in e.errors()
                ],
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

    model_config = ConfigDict(from_attributes=True)
