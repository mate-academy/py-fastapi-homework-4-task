from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from database import ActivationTokenModel
from schemas.accounts import PasswordResetSchema, TokenRefreshSchema, ActivationTokenSchema
from src.validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class UserProfileSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    avatar: str
    gender: str
    date_of_birth: date
    info: str | None = None

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str):
        validate_name(value)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value: str):
        validate_name(value)

    @field_validator("gender")
    @classmethod
    def validate_profile_gender(cls, value: str):
        validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date):
        validate_birth_date(value)


class UserSchema(BaseModel):
    id: int
    email: str
    _hashed_password: str
    is_active: bool
    created_at: date
    updated_at: date
    group_id: int
    group: str
    activation_token: ActivationTokenSchema
    password_reset_token: PasswordResetSchema
    refresh_tokens: TokenRefreshSchema
    profile: UserProfileSchema


class UserCreate(UserSchema):
    pass
