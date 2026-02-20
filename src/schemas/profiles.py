from fastapi import APIRouter
from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)

router = APIRouter()


class ProfileCreateRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        try:
            validate_name(value)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "value_error",
                        "loc": ["first_name"],
                        "msg": str(e),
                        "input": value,
                    }
                ],
            )
        return value.lower().strip()

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value: str) -> str:
        try:
            validate_name(value)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "value_error",
                        "loc": ["last_name"],
                        "msg": str(e),
                        "input": value,
                    }
                ],
            )
        return value.lower().strip()

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        try:
            validate_gender(value)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "value_error",
                        "loc": ["gender"],
                        "msg": str(e),
                        "input": value,
                    }
                ],
            )
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, value):
        try:
            validate_birth_date(value)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "value_error",
                        "loc": ["date_of_birth"],
                        "msg": str(e),
                        "input": str(value),
                    }
                ],
            )
        return value

    @field_validator("info")
    @classmethod
    def validate_info_field(cls, value):
        clean_info = value.strip()
        if not clean_info:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "value_error",
                        "loc": ["info"],
                        "msg": "Info field cannot be empty or contain only spaces.",
                        "input": value,
                    }
                ],
            )
        return clean_info

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        try:
            validate_image(value)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "value_error",
                        "loc": ["avatar"],
                        "msg": str(e),
                        "input": value.filename,
                    }
                ],
            )
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
    ) -> "ProfileCreateRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )


class ProfileCreateResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
