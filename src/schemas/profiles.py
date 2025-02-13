from datetime import date

from fastapi import UploadFile
from pydantic import BaseModel, field_validator, Field

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

from database.models.accounts import GenderEnum

from schemas.examples.profiles import profile_creation_schema_example, profile_response_schema_example


class ProfileSchema(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                profile_creation_schema_example
            ]
        },
    }

    # @field_validator("first_name", "last_name")
    # @classmethod
    # def validate_names(cls, value):
    #     return validate_name(value)
    #
    # @field_validator("gender")
    # @classmethod
    # def validate_gender_in(cls, value):
    #     return validate_gender(value)
    #
    # @field_validator("date_of_birth")
    # @classmethod
    # def validate_date_of_birth(cls, value):
    #     return validate_birth_date(value)
    #
    # @field_validator("info")
    # @classmethod
    # def validate_info(cls, value):
#     if len(" ".join(value.split())) == 0:
#         raise ValueError("Info: Cannot be empty or consist only of spaces.")
#     return value


class ProfileResponseSchema(ProfileSchema):
    id: int
    user_id: int = Field(..., description="Unique user identifier")
    avatar: str = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                profile_response_schema_example
            ]
        },
    }
