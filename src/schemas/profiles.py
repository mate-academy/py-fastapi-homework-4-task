from datetime import date

from fastapi import File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError, field_validator

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    model_config = {
        "arbitrary_types_allowed": True
    }

    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
        return value

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_date_of_birth(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        return value

    @classmethod
    def from_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(""),
        avatar: UploadFile = File(...),
    ) -> "ProfileCreateSchema":
        """
        Build the schema from multipart/form-data fields.

        FastAPI treats an empty form string as a missing value, so `info`
        has an empty default: the validator then returns a clear error.
        Validation errors are converted into an HTTP 422 response.
        """
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "loc": list(item["loc"]),
                        "msg": item["msg"],
                        "type": item["type"],
                    }
                    for item in error.errors()
                ],
            ) from error


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str

    model_config = {
        "from_attributes": True
    }
