from datetime import date
from typing import Any

from fastapi import Form, File, UploadFile
from pydantic import BaseModel


class ProfileRequestForm(BaseModel):
    """
    Schema for profile creation request form data.
    Handles validation of user profile information including file upload.
    """
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...)
    ) -> Any:
        """
        Factory method to create ProfileRequestForm from form data.
        This allows FastAPI to handle multipart/form-data requests.
        Returns:
            ProfileRequestForm instance with form data
        """
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )


class ProfileResponseSchema(BaseModel):
    """
    Schema for profile response data.
    Used to serialize profile information for API responses.
    """
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
