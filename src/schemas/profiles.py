from datetime import date
from typing import Optional

from fastapi import UploadFile, File, HTTPException
from pydantic import BaseModel, field_validator

from validation.profile import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

class ProfileRequestSchema(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[date]
    info: Optional[str]
    avatar: Optional[UploadFile]

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str):
        try:
            validate_name(value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return value


    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str):
        try:
            validate_gender(value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date):
        try:
            validate_birth_date(value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        print(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile):
        try:
            validate_image(value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str):
        if not value.strip():
            raise HTTPException(
                status_code=422,
                detail="Info field cannot be empty or contain only spaces."
            )
        return value
