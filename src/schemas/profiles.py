from datetime import datetime, date
from typing import Any

from fastapi import Form, File, UploadFile, HTTPException, status
from pydantic import BaseModel, field_validator

from validation.profile import validate_name, validate_image, validate_gender, validate_birth_date


class ProfileRequestForm(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
            cls,
            first_name: str = Form(),
            last_name: str = Form(),
            gender: str = Form(),
            date_of_birth: date = Form(),
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

    @staticmethod
    def validate_field(value, validation_func):
        if value:
            try:
                validation_func(value)
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(error)
                )
        return value

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_field(cls, value: str) -> str:
        return cls.validate_field(value, validate_name)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        return cls.validate_field(value, validate_gender)

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        return cls.validate_field(value, validate_birth_date)

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        if not value.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Info field cannot be empty or contain only spaces."
            )
        return value

    @field_validator("avatar")
    @classmethod
    def validate_image(cls, value: UploadFile) -> UploadFile:
        return cls.validate_field(value, validate_image)


class ProfileResponseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True
    }
