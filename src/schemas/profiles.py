from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator, field_serializer, ConfigDict
from database.models.accounts import GenderEnum
from config import get_settings

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


settings = get_settings()


class ProfileBaseSchema(BaseModel):
    first_name: Optional[str] = Form(None)
    last_name: Optional[str] = Form(None)
    gender: Optional[GenderEnum] = Form(None)
    date_of_birth: Optional[date] = Form(None)
    info: Optional[str] = Form(None)


# class ProfileRequestSchema(ProfileBaseSchema):

#     avatar: Optional[UploadFile] = File(None)

#     @field_validator("first_name")
#     @classmethod
#     def validate_first_name(cls, value):
#         if value:
#             validate_name(value)
#         return value

#     @field_validator("last_name")
#     @classmethod
#     def validate_last_name(cls, value):
#         if value:
#             validate_name(value)
#         return value

#     @field_validator("avatar")
#     @classmethod
#     def validate_image(cls, value):
#         if value:
#             validate_image(value)
#         return value

#     @field_validator("gender")
#     @classmethod
#     def validate_gender(cls, value):
#         if value:
#             validate_gender(value)
#         return value

#     @field_validator("date_of_birth")
#     @classmethod
#     def validate_birth_date(cls, value):
#         if value:
#             validate_birth_date(value)
#         return value


class ProfileResponseSchema(ProfileBaseSchema):
    id: int
    user_id: int
    avatar: Optional[str] = None

    model_config: ConfigDict = ConfigDict(from_attributes=True)

    @field_serializer("avatar")
    def serialize_avatar(self, avatar: str, _info):
        if not avatar:
            return None
        return f"http://{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}/{settings.S3_BUCKET_NAME}/{avatar}"
