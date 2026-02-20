from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def from_form(
            cls,
            first_name: str = Form(),
            last_name: str = Form(),
            gender: str = Form(),
            date_of_birth: date = Form(),
            info: str = Form(),
            avatar: UploadFile = File()
    ) -> "ProfileRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        try:
            validate_name(value)
            return value.lower()
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value error",
                    "loc": ["first_name" if "first_name" in value else "last_name"],
                    "msg": str(e),
                    "input": value
                }]
            )

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        try:
            validate_gender(value)
            return value
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value error",
                    "loc": ["gender"],
                    "msg": str(e),
                    "input": value
                }]
            )

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        try:
            validate_birth_date(value)
            return value
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value error",
                    "loc": ["date_of_birth"],
                    "msg": str(e),
                    "input": str(value)
                }]
            )

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        new_info = value.strip()
        if not new_info:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value error",
                    "loc": ["info"],
                    "msg": "Info field cannot be empty or contain only spaces.",
                    "input": value
                }]
            )
        return new_info

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        try:
            validate_image(value)
            return value
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value error",
                    "loc": ["avatar"],
                    "msg": str(e),
                    "input": value.filename
                }]
            )


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl
