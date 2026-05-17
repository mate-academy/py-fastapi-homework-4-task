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
    def validate_names(cls, v):
        validate_name(v)
        return v.lower()

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, v):
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date_field(cls, v):
        validate_birth_date(v)
        return v

    @field_validator("info")
    @classmethod
    def validate_info(cls, v):
        if not v.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v):
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
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=e.errors(include_input=False, include_context=False)
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

    class Config:
        from_attributes = True
