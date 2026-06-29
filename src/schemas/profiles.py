from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status, Depends
from pydantic import BaseModel, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


async def get_profile_create_schema(
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(""),
    avatar: UploadFile = File(...)
):
    try:
        return ProfileCreateSchema(first_name, last_name, gender, date_of_birth, info, avatar)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


class ProfileCreateSchema:
    def __init__(
        self,
        first_name: str,
        last_name: str,
        gender: str,
        date_of_birth: date,
        info: str,
        avatar: UploadFile
    ):
        validate_name(first_name)
        validate_name(last_name)
        validate_gender(gender)
        validate_birth_date(date_of_birth)

        if not info or not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")

        validate_image(avatar)

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

    model_config = ConfigDict(from_attributes=True)
