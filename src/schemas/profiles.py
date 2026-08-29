from datetime import date

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, HttpUrl

from validation import (
    validate_birth_date,
    validate_gender,
    validate_image,
    validate_name,
)


class UserProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str | None
    avatar: UploadFile

    @classmethod
    def as_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str | None = Form(default=None),
        avatar: UploadFile = File(...),
    ) -> "UserProfileCreateSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )

    def validate_profile(self) -> None:
        validate_name(self.first_name)
        validate_name(self.last_name)
        validate_gender(self.gender)
        validate_birth_date(self.date_of_birth)
        validate_image(self.avatar)

        if self.info is None or not self.info.strip():
            raise ValueError(
                "Info field cannot be empty or contain only spaces."
            )


class UserProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: HttpUrl

    model_config = {
        "from_attributes": True,
    }
