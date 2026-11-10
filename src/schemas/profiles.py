from datetime import date

from fastapi import File, Form, HTTPException, UploadFile, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)

from database.models.accounts import GenderEnum
from validation import (
    validate_birth_date,
    validate_gender,
    validate_image,
    validate_name,
)


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        validate_name(value)
        return value.lower()

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )

        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
        return value

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(""),
        avatar: UploadFile = File(...),
    ) -> "ProfileCreateSchema":
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
            errors = error.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            )

            for item in errors:
                item["loc"] = ["body", *item["loc"]]

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=errors,
            ) from error


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: HttpUrl
