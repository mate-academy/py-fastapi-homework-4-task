from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, field_validator

from validation import (
    validate_birth_date,
    validate_gender,
    validate_image,
    validate_name,
)

router = APIRouter()


def _raise_422(field: str, msg: str, raw_input):
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[
            {
                "type": "value_error",
                "loc": [field],
                "msg": msg,
                "input": raw_input,
            }
        ],
    )


class ProfileCreateRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name")
    @classmethod
    def v_first_name(cls, v: str) -> str:
        try:
            validate_name(v)
        except ValueError as e:
            _raise_422("first_name", str(e), v)
        return v.lower().strip()

    @field_validator("last_name")
    @classmethod
    def v_last_name(cls, v: str) -> str:
        try:
            validate_name(v)
        except ValueError as e:
            _raise_422("last_name", str(e), v)
        return v.lower().strip()

    @field_validator("gender")
    @classmethod
    def v_gender(cls, v: str) -> str:
        try:
            validate_gender(v)
        except ValueError as e:
            _raise_422("gender", str(e), v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def v_birth_date(cls, v: date) -> date:
        try:
            validate_birth_date(v)
        except ValueError as e:
            _raise_422("date_of_birth", str(e), str(v))
        return v

    @field_validator("info")
    @classmethod
    def v_info(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            _raise_422(
                "info",
                "Info field cannot be empty or contain only spaces.",
                v,
            )
        return clean

    @field_validator("avatar")
    @classmethod
    def v_avatar(cls, v: UploadFile) -> UploadFile:
        try:
            validate_image(v)
        except ValueError as e:
            _raise_422("avatar", str(e), v.filename)
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
    ) -> "ProfileCreateRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )


class ProfileCreateResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
