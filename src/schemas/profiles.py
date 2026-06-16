from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, HttpUrl, Field

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreationSchema:
    def __init__(
        self,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...)
    ):
        info_cleaned = info.strip()
        if not info_cleaned:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Info field cannot be empty or contain only spaces."

            )
        try:
            validate_name(first_name)
            validate_name(last_name)
            validate_gender(gender)
            validate_birth_date(date_of_birth)
            validate_image(avatar)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        avatar.file.seek(0)

        self.first_name = first_name.lower()
        self.last_name = last_name.lower()
        self.gender = gender
        self.date_of_birth = date_of_birth
        self.info = info_cleaned
        self.avatar = avatar


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True
    }
