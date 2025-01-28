import datetime
from typing import Any, Optional
from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator
from starlette import status
from validation import validate_name, validate_birth_date, validate_image, validate_gender

class ProfileRequestForm(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    info: Optional[str] = None
    avatar: Optional[UploadFile] = None

    @classmethod
    def as_form(
            cls,
            first_name: Optional[str] = Form(None),
            last_name: Optional[str] = Form(None),
            gender: Optional[str] = Form(None),
            date_of_birth: Optional[datetime.date] = Form(None),
            info: Optional[str] = Form(None),
            avatar: Optional[UploadFile] = File(None)
    ) -> Any:
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: Optional[str], field: str) -> Optional[str]:
        if value:
            try:
                validate_name(value)
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid {field}: {str(error)}"
                )
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: Optional[str]) -> Optional[str]:
        if value:
            try:
                validate_gender(value)
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(error)
                )
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: Optional[datetime.date]) -> Optional[datetime.date]:
        if value:
            try:
                validate_birth_date(value)
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(error)
                )
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Info cannot be blank or consist only of whitespace."
            )
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: Optional[UploadFile]) -> Optional[UploadFile]:
        if value:
            try:
                validate_image(value)
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(error)
                )
        return value

class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: datetime.date
    info: str
    avatar: str
