from datetime import date

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    ConfigDict,
    HttpUrl,
    ValidationError,
    field_validator
)

from validation import (
    validate_birth_date,
    validate_gender,
    validate_image,
    validate_name,
)


class ProfileBaseSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_first_and_last_names(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        if not value or value.isspace():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        validate_birth_date(value)
        return value


class ProfileRequestSchema(ProfileBaseSchema):
    avatar: UploadFile

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: date = Form(),
        info: str = Form(),
        avatar: UploadFile = File(),
    ) -> "ProfileRequestSchema":
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
            raise RequestValidationError(error.errors()) from error

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        try:
            validate_image(value)
        except ValueError as error:
            if str(error) == "Image size exceeds 1 MB":
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from error

            raise

        return value


class ProfileResponseSchema(ProfileBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    avatar: HttpUrl
