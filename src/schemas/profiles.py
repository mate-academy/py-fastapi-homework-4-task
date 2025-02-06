import datetime
from typing import Any, Optional

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, field_validator


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
        avatar: Optional[UploadFile] = File(),
    ) -> Any:
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, char):
        if not char or char.isdigit():
            raise ValueError("First name must contain only alphabetic characters, spaces, or hyphens.")
        return char

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, char):
        if not char or char.isdigit():
            raise ValueError("Last name must contain only alphabetic characters, spaces, or hyphens.")
        return char

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, gender):
        allowed_genders = {"male", "female", "other"}
        if gender and gender.lower() not in allowed_genders:
            raise ValueError(f"Gender must be one of {allowed_genders}.")
        return gender

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, birth):
        if birth and birth > datetime.date.today():
            raise ValueError("Date of birth cannot be in the future.")
        if birth and (datetime.date.today() - birth).days < 18 * 365:
            raise ValueError("You must be at least 18 years old to register.")
        return birth

    @field_validator("info")
    @classmethod
    def validate_info(cls, info):
        if not info or not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return info

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, file):
        if file:
            allowed_extensions = {".jpg", ".jpeg", ".png"}
            filename = file.filename.lower()
            if not any(filename.endswith(ext) for ext in allowed_extensions):
                raise ValueError("Avatar must be an image file (.jpg, .jpeg, .png).")
        return file

    class Config:
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
        from_attributes = True
