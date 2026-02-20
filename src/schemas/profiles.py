from datetime import date
from typing import Annotated

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

from database.models.accounts import GenderEnum


async def profile(
        first_name: Annotated[str, Form()],
        last_name: Annotated[str, Form()],
        gender: Annotated[str, Form()],
        date_of_birth: Annotated[date, Form()],
        info: Annotated[str | None, Form()] = None,
        avatar: Annotated[UploadFile, File(...)] = None,
):
    if info is not None and not info.strip():
        raise HTTPException(status_code=422, detail="Info field cannot be empty or contain only spaces.")

    try:
        validate_name(first_name)
        validate_name(last_name)
        validate_gender(gender)
        validate_birth_date(date_of_birth)
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender,
        "date_of_birth": date_of_birth,
        "info": info,
        "avatar": avatar,
    }


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str | None = None
    avatar: HttpUrl | None = None
