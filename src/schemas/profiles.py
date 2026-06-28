from datetime import date

from pydantic import BaseModel, field_validator
from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str | None = None
    user_id: int | None = None
    model_config = {"from_attributes": True}

    @field_validator("first_name")
    @classmethod
    def check_first_name(cls, first_name):
        validate_name(first_name)

        return first_name.lower()

    @field_validator("last_name")
    @classmethod
    def check_last_name(cls, last_name):
        validate_name(last_name)
        return last_name.lower()

    @field_validator("gender")
    @classmethod
    def check_gender(cls, gender):
        validate_gender(gender)
        return gender

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, date_of_birth):
        validate_birth_date(date_of_birth)
        return date_of_birth
