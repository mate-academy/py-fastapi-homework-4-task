import re
from datetime import date
from io import BytesIO

from PIL import Image
from fastapi import UploadFile

from database.models.accounts import GenderEnum


def validate_name(name: str):
    if re.search(r"^[A-Za-z]*$", name) is None:
        raise ValueError(f"{name} contains non-english letters")


def validate_image(avatar: UploadFile) -> UploadFile:
    max_file_size = 1 * 1024 * 1024  # 1 MB
    allowed_content_types = ["image/jpeg", "image/png", "image/jpg"]
    allowed_extensions = (".jpg", ".jpeg", ".png")

    contents = avatar.file.read()
    avatar.file.seek(0)

    if len(contents) > max_file_size:
        raise ValueError("Image size exceeds 1 MB")

    content_type_valid = avatar.content_type in allowed_content_types
    extension_valid = avatar.filename and avatar.filename.lower().endswith(allowed_extensions)

    if not content_type_valid or not extension_valid:
        raise ValueError("Invalid image format")

    return avatar


def validate_gender(gender: str) -> None:
    if gender not in GenderEnum.__members__.values():
        raise ValueError(
            f"Gender must be one of: {', '.join(g.value for g in GenderEnum)}"
        )


def validate_birth_date(birth_date: date) -> None:
    if birth_date.year < 1900:
        raise ValueError("Invalid birth date - year must be greater than 1900.")

    age = (date.today() - birth_date).days // 365
    if age < 18:
        raise ValueError("You must be at least 18 years old to register.")
