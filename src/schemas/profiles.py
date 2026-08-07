from __future__ import annotations
from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileRequestFormSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def validate_first_name_and_last_name(cls, value: str) -> str:
        try:
            validate_name(value)
            return value
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.args
            )

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        try:
            validate_gender(value)
            return value
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.args
            )

    @field_validator("date_of_birth", mode="after")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        try:
            validate_birth_date(value)
            return value
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.args
            )

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        try:
            validate_image(value)
            return value
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.args
            )

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: date = Form(),
        info: str = Form(),
        avatar: UploadFile = File(),
    ) -> ProfileRequestFormSchema:
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )

    @field_validator("info", mode="before")
    @classmethod
    def validate_info(cls, value: str) -> str:
        if not value or value.count(" ") == len(value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Info field cannot be empty or contain only spaces."
            )

        return value


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: str
    info: str
    avatar: HttpUrl
