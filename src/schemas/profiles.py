from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, ValidationError

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info
)


class ProfileSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_first_name(cls, value):
        validate_name(value)

        return value.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value):
        validate_gender(value)

        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value):
        validate_birth_date(value)

        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        validate_info(value)

        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value) -> UploadFile:
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
            raise HTTPException(422, detail=e.__str__())

    class Config:
        arbitrary_types_allowed = True


class ProfileResponseSchema(BaseModel):
    id: int | None = None
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str

    class Config:
        from_attributes = True
