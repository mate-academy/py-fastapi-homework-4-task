import datetime
from typing import Any, Optional

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, field_validator

from validation import validate_name, validate_gender, validate_birth_date, validate_image


class ProfileRequestForm(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[datetime.date]
    info: Optional[str]
    avatar: Optional[UploadFile]

    @classmethod
    def as_form(
        cls,
        first_name: Optional[str] = Form(),
        last_name: Optional[str] = Form(),
        gender: Optional[str] = Form(),
        date_of_birth: Optional[datetime.date] = Form(),
        info: Optional[str] = Form(),
        avatar: Optional[UploadFile] = File(),
    ) -> Any:
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, char):
        validate_name(char)
        return char

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, char):
        validate_name(char)
        return char

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, gender):
        validate_gender(gender)
        return gender

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, birth):
        validate_birth_date(birth)
        return birth

    @field_validator("info")
    @classmethod
    def validate_info(cls, info):
        if not info or not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return info

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, file):
        validate_image(file)
        return file

    class Config:
        from_attributes = True


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[datetime.date]
    info: Optional[str]
    avatar: Optional[str]

    class Config:
        from_attributes = True
