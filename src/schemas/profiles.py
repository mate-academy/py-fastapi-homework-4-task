from datetime import date
from fastapi import Form, File, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator, ConfigDict, HttpUrl, ValidationError
from validation import validate_name, validate_gender, validate_birth_date, validate_image


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl

    model_config = ConfigDict(from_attributes=True)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def check_names(cls, v: str) -> str:
        validate_name(v)
        return v.lower().strip()

    @field_validator("gender")
    @classmethod
    def check_gender(cls, v: str) -> str:
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, v: date) -> date:
        validate_birth_date(v)
        return v

    @field_validator("info")
    @classmethod
    def check_info(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, v: UploadFile) -> UploadFile:
        validate_image(v)
        return v

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
    ):
        try:
            return cls(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar,
            )
        except ValidationError as e:
            errors = e.errors()
            for error in errors:
                error.pop("input", None)
                error.pop("ctx", None)

            raise RequestValidationError(errors)
