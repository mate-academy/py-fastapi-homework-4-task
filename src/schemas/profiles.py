from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError

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
    def validate_and_normalize_name(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("gender")
    @classmethod
    def validate_profile_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_profile_birth_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_profile_info(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("avatar")
    @classmethod
    def validate_profile_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
        return value

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ) -> "ProfileCreateSchema":
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl

    model_config = {
        "from_attributes": True
    }

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        return value
