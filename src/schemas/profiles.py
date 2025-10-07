from datetime import date
from typing import Optional

from fastapi import Form
from pydantic import BaseModel, field_serializer, ConfigDict
from config import get_settings


settings = get_settings()


class ProfileBaseSchema(BaseModel):
    first_name: Optional[str] = Form(None)
    last_name: Optional[str] = Form(None)
    gender: Optional[str] = Form(None)
    date_of_birth: Optional[date] = Form(None)
    info: Optional[str] = Form(None)


class ProfileResponseSchema(ProfileBaseSchema):
    id: int
    user_id: int
    avatar: Optional[str] = None

    model_config: ConfigDict = ConfigDict(from_attributes=True)

    @field_serializer("avatar")
    def serialize_avatar(self, avatar: str, _info):
        if not avatar:
            return None

        return f"{settings.S3_STORAGE_ENDPOINT}/{settings.S3_BUCKET_NAME}/{avatar}"
