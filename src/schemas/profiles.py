from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError

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
    avatar: UploadFile = File(...)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v):
        try:
            validate_name(v)
            return v.lower()
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v):
        try:
            validate_name(v)
            return v.lower()
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        try:
            validate_gender(v)
            return v
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v):
        try:
            validate_birth_date(v)
            return v
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v):
        try:
            validate_image(v)
            return v
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @field_validator("info")
    @classmethod
    def validate_info(cls, info: str):
        if len(info) == 0:
            raise HTTPException(status_code=422, detail="Info field cannot be empty or contain only spaces.")
        for char in info:
            if char != " ":
                return info
        raise HTTPException(status_code=422, detail="Info field cannot be empty or contain only spaces.")

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...)
    ) -> "ProfileRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
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
