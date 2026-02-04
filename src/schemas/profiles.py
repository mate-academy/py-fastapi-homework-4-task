import json
from datetime import date
from typing import Optional

from fastapi import Form, HTTPException, status
from pydantic import BaseModel, field_validator, ValidationError

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)
from database.models.accounts import GenderEnum


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        validate_name(v)
        return v

    @field_validator("gender")
    @classmethod
    def validate_genders(cls, v: str) -> str:
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_dates(cls, v: date) -> date:
        validate_birth_date(v)
        return v

    @field_validator("info")
    @classmethod
    def validate_infos(cls, v: str) -> str:
        if not v or v.isspace():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @classmethod
    def as_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...)
    ):
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=json.loads(e.json())
            )
