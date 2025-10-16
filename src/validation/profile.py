import re
from datetime import date
from io import BytesIO

from PIL import Image
from fastapi import UploadFile

from database.models.accounts import GenderEnum


def validate_name(name: str):
    """
    Validates that name contains only English letters and is not empty.
    """
    if not name or not name.strip():
        raise ValueError("Name cannot be empty or contain only spaces")

    if re.search(r"^[A-Za-z]+$", name) is None:
        raise ValueError(f"{name} contains non-english letters")


def validate_image(avatar: UploadFile) -> None:
    """
    Validates image format and size.
    """
    supported_image_formats = ["JPG", "JPEG", "PNG"]
    max_file_size = 1 * 1024 * 1024

    contents = avatar.file.read()
    if len(contents) > max_file_size:
        avatar.file.seek(0)
        raise ValueError("Image size exceeds 1 MB")

    try:
        image = Image.open(BytesIO(contents))
        image_format = image.format
        if image_format not in supported_image_formats:
            avatar.file.seek(0)
            raise ValueError(
                f"Unsupported image format: {image_format}. Use one of next: {supported_image_formats}"
            )
    except IOError:
        avatar.file.seek(0)
        raise ValueError("Invalid image format")
    finally:
        avatar.file.seek(0)


def validate_gender(gender: str) -> None:
    """
    Validates that gender is one of the allowed enum values.
    """
    valid_genders = [g.value for g in GenderEnum]
    if gender not in valid_genders:
        raise ValueError(f"Gender must be one of: {', '.join(valid_genders)}")


def validate_birth_date(birth_date: date) -> None:
    """
    Validates birth date (year >= 1900 and age >= 18).
    """
    if birth_date.year < 1900:
        raise ValueError("Invalid birth date - year must be greater than 1900.")

    age = (date.today() - birth_date).days // 365
    if age < 18:
        raise ValueError("You must be at least 18 years old to register.")


def validate_info(info: str) -> None:
    """
    Validates that info is not empty.
    """
    if not info or info.strip() == "":
        raise ValueError("Info field cannot be empty or contain only spaces.")
