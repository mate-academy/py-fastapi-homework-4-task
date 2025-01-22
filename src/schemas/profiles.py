import datetime
from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, field_validator
from database.models.accounts import GenderEnum
from validation import validate_birth_date, validate_gender, validate_image, validate_name


class ProfileRequestSchema(BaseModel):
    """
    Schema for profile creation request.
    Includes validation for all fields using both Pydantic and custom validation functions.
    The avatar field is handled as an UploadFile for proper file upload handling.
    """
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: datetime.date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> None:
        """Validates that the provided first and last names only contain English letters."""
        return validate_name(value)

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile) -> None:
        """
        Validates that the provided avatar is a valid image file.
        Checks that the file is a supported image format (JPG, JPEG, PNG) and
        does not exceed 1MB in size.
        """
        return validate_image(value)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: GenderEnum) -> None:
        """Validates that the provided gender is a valid GenderEnum value."""
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: datetime.date) -> None:
        """Validates that the provided date of birth is a valid date and that the user is at least 18 years old."""
        return validate_birth_date(value)


class ProfileResponseSchema(BaseModel):
    """
    Schema for profile response.
    Used when returning profile information after creation or retrieval.
    The avatar field contains the URL to the stored image in MinIO.
    """
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: datetime.date
    info: str
    avatar: str
    model_config = ConfigDict(from_attributes=True)
