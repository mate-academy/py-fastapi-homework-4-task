from datetime import date

from fastapi import UploadFile, Form, File
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    field_validator,
    ConfigDict,
    ValidationError
)

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_date_of_birth
)


class ProfileCreateRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        validate_name(value)
        return value.lower()

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value: GenderEnum) -> GenderEnum:
        validate_gender(value.value if isinstance(value, GenderEnum) else value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        validate_date_of_birth(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar_field(cls, value: UploadFile) -> UploadFile:
        validate_image(value)
        return value

    @classmethod
    async def as_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...),
    ) -> "ProfileCreateRequestSchema":
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
            raise RequestValidationError(error.errors())


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
