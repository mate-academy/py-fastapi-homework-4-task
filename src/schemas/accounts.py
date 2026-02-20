from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, constr

from database import accounts_validators


class BaseEmailPasswordSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = {
        "from_attributes": True
    }

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return accounts_validators.validate_password_strength(value)


class UserRegistrationRequestSchema(BaseEmailPasswordSchema):
    pass


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequestSchema(BaseEmailPasswordSchema):
    token: str


class UserLoginRequestSchema(BaseEmailPasswordSchema):
    pass


class UserLoginResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {
        "from_attributes": True
    }


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class MessageResponseSchema(BaseModel):
    message: str


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileBase(BaseModel):
    first_name: constr(min_length=1)
    last_name: constr(min_length=1)
    gender: Optional[str]
    birth_date: Optional[date]
    biography: Optional[str]


class Profile(ProfileBase):
    id: int
    user_id: int
    avatar_url: Optional[str]

    class Config:
        orm_mode = True


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: date
    updated_at: date
    group_id: int

    class Config:
        orm_mode = True
