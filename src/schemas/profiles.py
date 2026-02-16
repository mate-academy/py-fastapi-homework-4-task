from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, HttpUrl, Field, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = {"from_attributes": True}


class ProfileCreateFormSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    @classmethod
    def _validate_first_name(cls, v):
        if not v or v.isspace():
            raise ValueError("First name cannot be empty.")
        validate_name(v)
        return v.lower()

    @field_validator("last_name")
    @classmethod
    def _validate_last_name(cls, v: str):
        if not v or v.isspace():
            raise ValueError("First name cannot be empty.")
        validate_name(v)
        return v.lower()

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, v: str):
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _validate_birth_date(cls, v: date):
        validate_birth_date(v)
        return v

    @field_validator("info")
    @classmethod
    def _validate_info(cls, v: str):
        if not v or v.isspace():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @field_validator("avatar")
    @classmethod
    def _validate_avatar(cls, v: UploadFile):
        validate_image(v)
        return v

    @classmethod
    def as_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...)
    ):
        try:
            instance = cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar
            )
            return instance
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=str(e)
            ) from None
