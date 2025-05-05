import enum
from datetime import date
from typing import Annotated

from fastapi import UploadFile
from pydantic import BaseModel, BeforeValidator, ConfigDict

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)
from validation.profile import validate_info


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


# Write your code here
class UserProfileCreateRequestSchema(BaseModel):
    first_name: Annotated[str, BeforeValidator(validate_name)]
    last_name: Annotated[str, BeforeValidator(validate_name)]
    gender: Annotated[GenderEnum, BeforeValidator(validate_gender)]
    date_of_birth: Annotated[date, BeforeValidator(validate_birth_date)]
    info: Annotated[str, BeforeValidator(validate_info)]
    avatar: Annotated[UploadFile, BeforeValidator(validate_image)]


class UserProfileCreateResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    model_config = ConfigDict(from_attributes=True)
