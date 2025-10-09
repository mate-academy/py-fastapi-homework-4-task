from datetime import date

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import BaseModel, field_validator, ConfigDict, ValidationError

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date, validate_info
)


class RequestProfileSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def check_name(cls, value):
        validate_name(value)
        return value.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def check_gender(cls, value):
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_date_of_birth(cls, value):
        validate_birth_date(value)
        return value

    @field_validator("avatar")
    @classmethod
    def check_image(cls, value):
        validate_image(value)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value):
        validate_info(value)
        return value

    @classmethod
    def as_form(
            cls,
            first_name: str = Form(),
            last_name: str = Form(),
            gender: str = Form(),
            date_of_birth: date = Form(),
            info: str = Form(),
            avatar: UploadFile = File(),
    ):
        if not info.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Info field cannot be empty or contain only spaces."
            )
        try:
            profile_data = cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as err:
            custom_errors = [
                {"field": ".".join(str(x) for x in err["loc"]), "message": err["msg"]}
                for err in err.errors()
            ]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": custom_errors}
            )

        return profile_data


class ResponseProfileSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
