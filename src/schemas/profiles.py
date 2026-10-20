from datetime import date
from database.models.accounts import GenderEnum
from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ):
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=GenderEnum(gender),
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValueError as e:
            print(e)
            raise HTTPException(
                status_code=422, detail="Gender must be one of allowed values."
            )

    @field_validator("gender")
    @classmethod
    def gender_validator(cls, gender):
        validate_gender(gender)
        return gender.lower()


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int = None
    user_id: int = None
    first_name: str = None
    last_name: str = None
    gender: str = None
    date_of_birth: date = None
    info: str = None
    avatar: str = None
