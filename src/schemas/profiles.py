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
    #
    # @field_validator("first_name", "last_name")
    # @classmethod
    # def validate_first_name(cls, value):
    #     validate_name(value)
    #     return value
    #
    # # @field_validator("last_name")
    # # @classmethod
    # # def validate_last_name(cls, value):
    # #     validate_name(value)
    # #     return value
    #
    # @field_validator("gender")
    # @classmethod
    # def validate_gender(cls, value):
    #     validate_gender(value)
    #     return value
    #
    # @field_validator("date_of_birth")
    # @classmethod
    # def validate_date_of_birth(cls, value):
    #     validate_birth_date(value)
    #     return value
    #
    # @field_validator("info")
    # @classmethod
    # def validate_info(cls, value):
    #     if not value or not value.strip():
    #         raise ValueError("info cannot be empty")
    #     return value
    #
    # @field_validator("avatar")
    # @classmethod
    # def validate_avatar(cls, value):
    #     validate_image(value)
    #     return value


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
