import re
from datetime import date

from fastapi import UploadFile

from database.models.accounts import GenderEnum


def validate_name(name: str):
    if re.search(r'^[A-Za-z]*$', name) is None:
        raise ValueError(f'{name} contains non-english letters')
    return name.lower()


def validate_image(avatar: UploadFile) -> UploadFile:
    supported_image_formats = {
        "image/jpeg",
        "image/png",
    }
    max_file_size = 1 * 1024 * 1024

    contents = avatar.file.read()

    if len(contents) > max_file_size:
        raise ValueError("Image size exceeds 1 MB")

    if avatar.content_type not in supported_image_formats:
        raise ValueError("Invalid image format")

    avatar.file.seek(0)
    return avatar


def validate_gender(gender: str) -> None:
    if gender not in GenderEnum.__members__.values():
        raise ValueError(f"Gender must be one of: {', '.join(g.value for g in GenderEnum)}")
    return gender


def validate_birth_date(birth_date: date) -> None:
    if birth_date.year < 1900:
        raise ValueError('Invalid birth date - year must be greater than 1900.')

    age = (date.today() - birth_date).days // 365
    if age < 18:
        raise ValueError('You must be at least 18 years old to register.')
    return birth_date
