from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, HttpUrl

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
        try:
            validate_name(first_name)
            validate_name(last_name)
            validate_gender(gender)
            validate_birth_date(date_of_birth)
            if not info.strip():
                raise ValueError("Info cannot be empty or consist only of spaces.")
            validate_image(avatar)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        
        self.first_name = first_name
        self.last_name = last_name
        self.gender = gender
        self.date_of_birth = date_of_birth
        self.info = info
        self.avatar = avatar

class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True
    }
