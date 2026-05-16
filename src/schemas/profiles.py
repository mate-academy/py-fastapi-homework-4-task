from datetime import date

from pydantic import BaseModel, ConfigDict

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


def validate_name_field(value: str) -> str:
    validate_name(value)
    return value


def validate_gender_field(value: GenderEnum) -> GenderEnum:
    validate_gender(value)
    return value


def validate_birth_date_field(value: date) -> date:
    validate_birth_date(value)
    return value


def validate_info_field(value: str) -> str:
    if not value.strip():
        raise ValueError("Info field cannot be empty or contain only spaces.")
    return value


def validate_avatar(value):
    validate_image(value)
    return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str

    model_config = ConfigDict(from_attributes=True)
