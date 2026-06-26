from datetime import date

from fastapi import UploadFile, Form, File
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator, HttpUrl, ValidationError

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("first_name")
    @classmethod
    def valid_first_name(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("last_name")
    @classmethod
    def valid_last_name(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("gender")
    @classmethod
    def valid_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def valid_birth_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def valid_info(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )
        return value

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ) -> "ProfileRequestSchema":
        errors = []
        try:
            validate_image(avatar)
        except ValueError as e:
            errors.append(
                {
                    "type": "value_error",
                    "loc": ("body", "avatar"),
                    "msg": str(e),
                    "input": avatar.filename,
                }
            )
        instance = None
        try:
            instance = cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as e:
            for err in e.errors():
                errors.append(
                    {
                        "type": err["type"],
                        "loc": ("body", *[str(x) for x in err["loc"]]),
                        "msg": err["msg"],
                        "input": err.get("input"),
                    }
                )

        if errors:
            raise RequestValidationError(errors)

        return instance


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: HttpUrl

    model_config = {"from_attributes": True}
