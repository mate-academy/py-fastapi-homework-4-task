import re
from datetime import date
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from database.models.accounts import GenderEnum


def validate_name(name: str) -> None:
    if not name or re.fullmatch(r"[A-Za-z]+", name) is None:
        raise ValueError(f"{name} contains non-english letters")


def validate_image(avatar: UploadFile) -> None:
    supported_image_formats = ["JPG", "JPEG", "PNG"]
    max_file_size = 1 * 1024 * 1024

    try:
        avatar.file.seek(0)
        contents = avatar.file.read(max_file_size + 1)

        if len(contents) > max_file_size:
            raise ValueError("Image size exceeds 1 MB")

        try:
            with Image.open(BytesIO(contents)) as image:
                image_format = image.format

                if image_format not in supported_image_formats:
                    raise ValueError(
                        f"Unsupported image format: {image_format}. "
                        f"Use one of next: {supported_image_formats}"
                    )

                image.verify()

        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            Image.DecompressionBombError,
        ) as error:
            raise ValueError("Invalid image format") from error

    finally:
        avatar.file.seek(0)


def validate_gender(gender: str) -> None:
    allowed_genders = {item.value for item in GenderEnum}

    if gender not in allowed_genders:
        raise ValueError(
            f"Gender must be one of: "
            f"{', '.join(item.value for item in GenderEnum)}"
        )


def validate_birth_date(birth_date: date) -> None:
    if birth_date.year < 1900:
        raise ValueError(
            "Invalid birth date - year must be greater than 1900."
        )

    today = date.today()

    age = today.year - birth_date.year
    age -= (today.month, today.day) < (
        birth_date.month,
        birth_date.day,
    )

    if age < 18:
        raise ValueError(
            "You must be at least 18 years old to register."
        )
