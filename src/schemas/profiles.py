from pydantic import BaseModel, validator, field_validator
from fastapi import UploadFile, File, Form, HTTPException
import datetime
from typing import Optional, Any
from validation.profile import validate_gender, validate_image, validate_name, validate_birth_date


class ProfileRequestForm(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[datetime.date]
    info: Optional[str]
    avatar: Optional[UploadFile]

    @classmethod
    def as_form(
        cls,
        first_name: Optional[str] = Form(),
        last_name: Optional[str] = Form(),
        gender: Optional[str] = Form(),
        date_of_birth: Optional[datetime.date] = Form(),
        info: Optional[str] = Form(),
        avatar: Optional[UploadFile] = File()
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


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[datetime.date]
    info: Optional[str]
    avatar: Optional[str]

    class Config:
        orm_mode = True
        from_attributes = True
