from fastapi import UploadFile, Form, File
from pydantic import BaseModel, validator, field_validator
import datetime
from typing import Optional, Any
from validation.profile import validate_gender, validate_image, validate_name, validate_birth_date

class ProfileRequestSchema(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[datetime.date]
    info: Optional[str]
    avatar: str

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        validate_name(value)
        return value

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value):
        validate_name(value)
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value):
        validate_birth_date(value)
        return value


    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value):
        #validate_image(value)
        return value


class ProfileResponseSchema(ProfileRequestSchema):
    id: int
    user_id: int


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
            avatar: UploadFile = File()
    ) -> Any:
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        validate_name(value)

        return value
