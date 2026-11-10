from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict, ValidationError

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileBaseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str


class ProfileCreateRequestSchema(ProfileBaseSchema):
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, name_field: str):
        validate_name(name_field)
        return name_field.lower()

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, gender_field: str):
        validate_gender(gender_field)
        return gender_field

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, date_of_birth_field: date):
        validate_birth_date(date_of_birth_field)
        return date_of_birth_field

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, avatar_field: UploadFile):
        validate_image(avatar_field)
        return avatar_field

    @field_validator("info")
    @classmethod
    def validate_info(cls, info_field: str):
        if not info_field.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return info_field

    @classmethod
    def from_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...),
    ) -> "ProfileCreateRequestSchema":
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[err["msg"] for err in e.errors()],
            )


class ProfileResponseSchema(ProfileBaseSchema):
    id: int
    user_id: int
    avatar: HttpUrl

    model_config = ConfigDict(from_attributes=True)
