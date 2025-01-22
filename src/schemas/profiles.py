import datetime
from typing import Any

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, ConfigDict


class ProfileRequestForm(BaseModel):
    """
    Pydantic model for handling user profile form data with file upload.
    Provides form validation and conversion of multipart form data into a structured model.
    The as_form classmethod allows this model to be used with FastAPI's form handling.
    """

    first_name: str
    last_name: str
    gender: str
    date_of_birth: datetime.date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: datetime.date = Form(),
        info: str = Form(),
        avatar: UploadFile = File(),
    ) -> Any:
        """Creates a ProfileRequestForm instance from form data."""
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )

    model_config = ConfigDict(from_attributes=True)
