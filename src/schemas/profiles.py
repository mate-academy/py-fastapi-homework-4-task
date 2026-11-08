from datetime import date

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl, field_validator, model_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @model_validator(mode="after")
    def check_avatar(self) -> "ProfileCreateSchema":
        try:
            validate_image(self.avatar)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
        return self


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl
