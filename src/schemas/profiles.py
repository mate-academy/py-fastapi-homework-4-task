from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, Field

from database.models.accounts import GenderEnum


class ProfileBaseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str = Field(...)
    avatar: UploadFile = Field(...)


class ProfileResponseSchema(ProfileBaseSchema):
    id: int
    avatar: str

    class Config:
        from_attributes = True


class ProfileCreateSchema(ProfileBaseSchema):
    pass

    # @field_validator("info")
    # @classmethod
    # def validate_profile_info(cls, value):
    #     try:
    #         validate_info(value)
    #     except ValueError as error:
    #         raise HTTPException(status_code=422, detail=str(error))
    #
    # @field_validator("first_name", "last_name")
    # @classmethod
    # def validate_profile_first_and_last_name(cls, value):
    #     try:
    #         validate_name(value)
    #     except ValueError as error:
    #         raise HTTPException(status_code=422, detail=str(error))
    #
    # @field_validator("gender", mode="before")
    # @classmethod
    # def validate_profile_gender(cls, value):
    #     try:
    #         validate_gender(value)
    #     except ValueError as error:
    #         raise HTTPException(status_code=422, detail=str(error))
    #     return value
    #
    # @field_validator("date_of_birth")
    # @classmethod
    # def validate_profile_date_of_birth(cls, value):
    #     try:
    #         validate_birth_date(value)
    #     except ValueError as error:
    #         raise HTTPException(status_code=422, detail=str(error))
    #
    # @field_validator("avatar")
    # @classmethod
    # def validate_profile_avatar(cls, value):
    #     try:
    #         validate_image(value)
    #     except ValueError as error:
    #         raise HTTPException(status_code=422, detail=str(error))
