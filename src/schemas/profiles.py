from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_info,
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
    info: str
    avatar: str


class ProfileRequestSchema:
    def __init__(
        self,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ):
        self.first_name = first_name
        self.last_name = last_name
        self.gender = gender
        self.date_of_birth = date_of_birth
        self.info = info
        self.avatar = avatar

        self._validate()

        self.first_name = self.first_name.lower()
        self.last_name = self.last_name.lower()

    def _validate(self):
        validators = (
            (validate_name, self.first_name),
            (validate_name, self.last_name),
            (validate_gender, self.gender),
            (validate_birth_date, self.date_of_birth),
            (validate_info, self.info),
            (validate_image, self.avatar),
        )

        try:
            for validator, arg in validators:
                validator(arg)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
            ) from e
