from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

# Write your code here
class ProfileResponseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl


    @classmethod
    @field_validator("first_name")
    def check_first_name(cls, value):
        validate_name(value)
        return value

    @classmethod
    @field_validator("last_name")
    def check_last_name(cls, value):
        validate_name(value)
        return value

    @classmethod
    @field_validator("gender")
    def check_gender(cls, value):
        validate_gender(value)
        return value

    @classmethod
    @field_validator("birth_date")
    def check_birth_date(cls, value):
        validate_birth_date(value)
        return value

    @classmethod
    @field_validator("info")
    def check_info(cls, value):

        if not len(value) <= 0:
            contain = [i for i in value if i != " "]
            if len(contain) > 0:
                return value
        raise HTTPException(status_code=400, detail="Invalid info")

    @classmethod
    @field_validator("avatar")
    def check_avatar(cls, value):
        validate_image(value)
        return value
