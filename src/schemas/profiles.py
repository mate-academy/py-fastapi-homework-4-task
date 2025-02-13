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


class ProfileResponseSchema(ProfileSchema):
    id: int
    user_id: int = Field(..., description="Unique user identifier")
    avatar: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                profile_response_schema_example
            ]
        },
    }
