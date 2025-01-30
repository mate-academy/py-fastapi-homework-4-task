from pydantic import BaseModel
from fastapi import UploadFile, File, Form
import datetime
from typing import Any


class ProfileRequestForm(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: datetime.date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: datetime.date = Form(),
        info: str = Form(),
        avatar: UploadFile = File()
    ) -> Any:
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )

    class Config:
        orm_mode = True
        from_attributes = True
