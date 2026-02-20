from datetime import date
from typing import Annotated

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)
from validation.profile import validate_info


class ProfileCreationRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    # use this in endpoint - Depends(ProfileCreationRequestSchema.from_form)
    avatar: UploadFile

    @classmethod
    def from_form(
        cls,
        first_name: Annotated[str, Form(...)],
        last_name: Annotated[str, Form(...)],
        gender: Annotated[str, Form(...)] ,
        date_of_birth: Annotated[date, Form(...)] ,
        info: Annotated[str, Form(...)] ,
        avatar: Annotated[UploadFile, File(...)]
    ) -> "ProfileCreationRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_fields(cls, value: str) -> str:
        try:
            validate_name(value)
            return value.lower()
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            )

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: str) -> str:
        try:
            validate_gender(value)
            return value
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            )

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date_field(cls, value: date) -> date:
        try:
            validate_birth_date(value)
            return value
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            )

    @field_validator("avatar")
    @classmethod
    def validate_image_field(cls, file: UploadFile) -> UploadFile:
        try:
            validate_image(file)
            return file
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            )

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: str) -> str:
        try:
            validate_info(value)
            return value
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            )


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl

    model_config = {"from_attributes": True}
