import re
from datetime import date
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile

from database.models.accounts import GenderEnum

SUPPORTED_FORMATS = {"JPG", "JPEG", "PNG"}


def validate_name(name: str) -> None:
    if re.search(r"^[A-Za-z]*$", name) is None:
        raise ValueError(f"{name} contains non-english letters")


def validate_image(avatar: UploadFile, max_size: int = 1 * 1024 * 1024) -> bytes:
    data = avatar.file.read()
    avatar.file.seek(0)

    if len(data) > max_size:
        raise ValueError("Image size exceeds 1 MB")

    try:
        img = Image.open(BytesIO(data))
        fmt = (img.format or "").upper()
    except (UnidentifiedImageError, OSError):
        raise ValueError("Invalid image format")

    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image format: {fmt}. Use one of {sorted(SUPPORTED_FORMATS)}")
    return data


def validate_gender(gender: str) -> None:
    allowed = [g.value for g in GenderEnum]
    if gender not in allowed:
        raise ValueError(f"Gender must be one of: {', '.join(allowed)}")


def validate_birth_date(birth_date: date) -> None:
    if birth_date.year < 1900:
        raise ValueError("Invalid birth date - year must be greater than 1900.")

    age = (date.today() - birth_date).days // 365
    if age < 18:
        raise ValueError("You must be at least 18 years old to register.")
