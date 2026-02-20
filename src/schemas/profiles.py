from datetime import date

from pydantic import ConfigDict
from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema:
    def __init__(
            self,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...)
    ):
        validate_name(first_name)
        validate_name(last_name)
        validate_gender(gender)
        validate_birth_date(date_of_birth)
        if not info.strip():
            raise ValueError("Info cannot be empty or only spaces.")

        validate_image(avatar)

        self.first_name = first_name
        self.last_name = last_name
        self.gender = gender
        self.date_of_birth = date_of_birth
        self.info = info
        self.avatar = avatar


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
