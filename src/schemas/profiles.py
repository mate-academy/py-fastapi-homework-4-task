from datetime import date

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, ConfigDict, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info,
)


class ProfileCreationSchema(BaseModel):
    first_name: str
    last_name: str
    avatar: UploadFile
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        return validate_name(name)

    @field_validator("avatar")
    @classmethod
    def validate_image(cls, avatar: UploadFile) -> None:
        return validate_image(avatar)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, gender: str) -> str:
        return validate_gender(gender)

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, birth_date: date) -> None:
        return validate_birth_date(birth_date)

    @field_validator("info")
    @classmethod
    def validate_info(cls, info: str) -> str:
        return validate_info(info)

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ) -> "ProfileCreationSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    avatar: str
    gender: str
    date_of_birth: date
    info: str
