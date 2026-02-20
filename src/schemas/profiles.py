from datetime import date
from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, ConfigDict

from validation.profile import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

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
            first_name = validate_name(name=first_name)
            last_name = validate_name(name=last_name)
            gender = validate_gender(gender=gender)
            date_of_birth = validate_birth_date(birth_date=date_of_birth)
            info = validate_info(info=info)
            avatar = validate_image(avatar=avatar)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=str(e)
            )
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
    avatar: str

    model_config = ConfigDict(from_attributes=True)
