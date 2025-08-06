from datetime import date
from typing import Annotated

from fastapi import UploadFile, Form, File, HTTPException, status
from pydantic import (
    BaseModel,
    field_validator,
    HttpUrl,
    ConfigDict,
)

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
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def validate_names(cls, value: str) -> str:
        try:
            validate_name(value)
            return value.strip().lower()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        try:
            validate_gender(value)
            return value
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def validate_date_of_birth_field(cls, value: date) -> date:
        try:
            validate_birth_date(value)
            return value
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    @field_validator("info", mode="before")
    @classmethod
    def validate_info_field(cls, value: str) -> str:
        if not value.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Info field cannot be empty or contain only spaces.",
            )
        return value

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar_file(cls, value: UploadFile) -> UploadFile:
        try:
            validate_image(value)
            return value
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    @classmethod
    def as_form(
        cls,
        first_name: Annotated[str, Form()],
        last_name: Annotated[str, Form()],
        gender: Annotated[GenderEnum, Form()],
        date_of_birth: Annotated[date, Form()],
        info: Annotated[str, Form()],
        avatar: Annotated[UploadFile, File()],
    ) -> "ProfileRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )


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
