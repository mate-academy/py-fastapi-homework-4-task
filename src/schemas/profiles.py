from datetime import date

from fastapi import UploadFile, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class BaseProfileSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_field(cls, name: str) -> str:
        try:
            validate_name(name)
            return name.lower()
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, gender: str) -> str:
        try:
            validate_gender(gender)
            return gender
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, date_of_birth: date) -> date:
        try:
            validate_birth_date(date_of_birth)
            return date_of_birth
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("info")
    @classmethod
    def validate_info_field(cls, value: str) -> str:
        if not len(value.strip()) > 0:
            raise HTTPException(
                status_code=422,
                detail="Info field cannot be empty or contain only spaces.",
            )
        return value.strip()


class ProfileCreateRequestSchema(BaseProfileSchema):
    avatar: UploadFile

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, avatar: UploadFile) -> UploadFile:
        try:
            validate_image(avatar)
            return avatar
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


class ProfileResponseSchema(BaseProfileSchema):
    id: int
    avatar: HttpUrl
