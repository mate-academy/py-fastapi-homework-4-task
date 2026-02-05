from datetime import date
from typing import Annotated, Optional

from fastapi import UploadFile
from pydantic import BaseModel, HttpUrl, BeforeValidator

from validation.profile import (
    validate_name,
    validate_gender,
    validate_birth_date,
    validate_image,
)


def validate_name_field(value: str) -> str:
    validate_name(value)
    return value


def validate_gender_field(value: str) -> str:
    validate_gender(value)
    return value


def validate_birth_date_field(value: date) -> date:
    validate_birth_date(value)
    return value


def validate_info_field(value: str) -> str:
    if not value or value.strip() == "":
        raise ValueError("Info field cannot be empty or contain only spaces.")
    return value


def validate_avatar_field(value: Optional[UploadFile]) -> Optional[UploadFile]:
    if value is None:
        return None
    try:
        validate_image(value)
        return value
    except ValueError as exc:
        raise ValueError(str(exc))


class ProfileCreateSchema(BaseModel):
    first_name: Annotated[str, BeforeValidator(validate_name_field)]
    last_name: Annotated[str, BeforeValidator(validate_name_field)]
    gender: Annotated[str, BeforeValidator(validate_gender_field)]
    date_of_birth: Annotated[date, BeforeValidator(validate_birth_date_field)]
    info: Annotated[str, BeforeValidator(validate_info_field)]
    avatar: Annotated[Optional[UploadFile], BeforeValidator(validate_avatar_field)]


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl

    model_config = {
        "from_attributes": True
    }
