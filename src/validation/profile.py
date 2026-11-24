import re
from datetime import date
from io import BytesIO

from PIL import Image
from fastapi import UploadFile

from database.models.accounts import GenderEnum


def validate_name(name: str):
    if re.fullmatch(r"[A-Za-z]+", name) is None:
        raise ValueError(f"{name} contains non-english letters")
    return name


def validate_image(avatar: UploadFile) -> UploadFile:
    supported_image_formats = ["JPEG", "PNG"]
    max_file_size = 1 * 1024 * 1024

    contents = avatar.file.read(max_file_size + 1)

    avatar.file.seek(0)

    if len(contents) > max_file_size:
        raise ValueError("Image size exceeds 1 MB")

    try:
        image = Image.open(BytesIO(contents))
        image_format = image.format

        if image_format not in supported_image_formats:
            raise ValueError(
                f"Unsupported image format: {image_format}. "
                f"Use one of: {supported_image_formats}"
            )

        image.verify()

    except (OSError, Image.DecompressionBombError):
        raise ValueError("Invalid image format")

    return avatar


def validate_gender(gender: str):
    if gender not in [g.value for g in GenderEnum]:
        raise ValueError(
            f"Gender must be one of: {', '.join(g.value for g in GenderEnum)}"
        )
    return gender


def validate_birth_date(birth_date: date):
    today = date.today()

    if birth_date.year < 1900:
        raise ValueError(
            "Invalid birth date - year must be greater than 1900."
        )

    if birth_date > today:
        raise ValueError("Birth date cannot be in the future.")

    age = today.year - birth_date.year

    if (today.month, today.day) < (
        birth_date.month, birth_date.day
    ):
        age -= 1

    if age < 18:
        raise ValueError(
            "You must be at least 18 years old to register."
        )

    return birth_date
