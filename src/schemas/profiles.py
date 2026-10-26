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


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def from_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...)
    ) -> "ProfileCreateSchema":
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=[{"loc": err["loc"], "msg": err["msg"]} for err in error.errors()]
            )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_field(cls, name: str) -> str:
        validate_name(name)
        return name.lower()

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, gender: str) -> str:
        validate_gender(gender)
        return gender

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, date_of_birth: date) -> date:
        validate_birth_date(date_of_birth)
        return date_of_birth

    @field_validator("info")
    @classmethod
    def validate_info_field(cls, info: str) -> str:
        cleaned_info = info.strip()
        if not cleaned_info:
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return cleaned_info

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, avatar: UploadFile) -> UploadFile:
        validate_image(avatar)
        return avatar


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl
