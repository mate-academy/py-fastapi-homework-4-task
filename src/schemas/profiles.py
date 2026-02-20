from datetime import date

from fastapi import Form, HTTPException, UploadFile, File
from pydantic import BaseModel

from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
    validate_image,
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile | None

    @classmethod
    def from_form(
        cls,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile | None = File(None),
    ) -> "ProfileCreateSchema":
        try:
            validate_name(first_name)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        try:
            validate_name(last_name)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        try:
            validate_gender(gender)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        try:
            validate_birth_date(date_of_birth)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        if not info.strip():
            raise HTTPException(
                status_code=422,
                detail="Info field cannot be empty or contain only spaces.",
            )

        try:
            validate_image(avatar)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        return cls(
            first_name=first_name.lower(),
            last_name=last_name.lower(),
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar,
        )


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: str | date
    info: str
    avatar: str

    model_config = {"from_attributes": True}
