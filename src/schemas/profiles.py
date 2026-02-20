from typing import Optional
from datetime import date
from pydantic import BaseModel, Field
from src.database.models.accounts import GenderEnum


class UserProfileBase(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(UserProfileBase):
    pass


class UserProfileOut(UserProfileBase):
    id: int

    class Config:
        orm_mode = True