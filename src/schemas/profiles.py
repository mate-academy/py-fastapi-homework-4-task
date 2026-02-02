from datetime import date
from typing import Annotated

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str | None
    avatar: HttpUrl | None

    class Config:
        from_attributes = True


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str | None
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    def validate_names(cls, v):
        validate_name(v)
        return v.lower()

    @field_validator("gender")
    def validate_gender_field(cls, v):
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    def validate_birth_date_field(cls, v):
        validate_birth_date(v)
        return v

    @field_validator("info")
    def validate_info_field(cls, v):
        if v is not None and (not v or v.isspace()):
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @field_validator("avatar")
    def validate_avatar_field(cls, v):
        validate_image(v)
        return v

    @classmethod
    def as_form(
        cls,
        first_name: Annotated[str, Form()],
        last_name: Annotated[str, Form()],
        gender: Annotated[str, Form()],
        date_of_birth: Annotated[date, Form()],
        info: Annotated[str | None, Form()] = None,
        avatar: Annotated[UploadFile, File()] = None,
    ):
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )
