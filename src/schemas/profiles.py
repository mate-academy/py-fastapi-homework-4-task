from datetime import date
from typing import Optional

from fastapi import UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class CreateProfileRequestSchema:
    def __init__(
        self,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: Optional[str] = Form(default=None),
        avatar: UploadFile = File(...),
    ):
        errors = []

        try:
            validate_name(first_name)
        except ValueError as e:
            errors.append({"loc": ["body", "first_name"], "msg": str(e), "type": "value_error"})

        try:
            validate_name(last_name)
        except ValueError as e:
            errors.append({"loc": ["body", "last_name"], "msg": str(e), "type": "value_error"})

        try:
            validate_gender(gender)
        except ValueError as e:
            errors.append({"loc": ["body", "gender"], "msg": str(e), "type": "value_error"})

        try:
            validate_birth_date(date_of_birth)
        except ValueError as e:
            errors.append({"loc": ["body", "date_of_birth"], "msg": str(e), "type": "value_error"})

        if not info or not info.strip():
            errors.append({
                "loc": ["body", "info"],
                "msg": "Info field cannot be empty or contain only spaces.",
                "type": "value_error"
            })

        try:
            validate_image(avatar)
        except ValueError as e:
            errors.append({"loc": ["body", "avatar"], "msg": str(e), "type": "value_error"})

        if errors:
            raise HTTPException(status_code=422, detail=errors)

        self.first_name = first_name.lower()
        self.last_name = last_name.lower()
        self.gender = gender
        self.date_of_birth = date_of_birth
        self.info = info
        self.avatar = avatar


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[date]
    info: Optional[str]
    avatar: Optional[str]

    model_config = {"from_attributes": True}
