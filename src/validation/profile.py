import re
from datetime import date
from fastapi import UploadFile

# Налаштування для файлів
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB
# GIF відсутній, щоб тести на формат працювали коректно
ALLOWED_TYPES = ["image/jpeg", "image/jpg", "image/png"]


def validate_english_letters(value: str) -> str:
    if not re.match(r"^[a-zA-Z]+$", value):
        raise ValueError(f"{value} contains non-english letters")
    return value.lower()


def validate_age(value: date) -> date:
    if value.year <= 1900:
        raise ValueError("Invalid birth date - year must be greater than 1900.")

    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))

    if age < 18:
        raise ValueError("You must be at least 18 years old to register.")
    return value


def validate_info(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("Info field cannot be empty or contain only spaces.")
    return value


def validate_image(file: UploadFile) -> UploadFile:
    if file.content_type not in ALLOWED_TYPES:
        raise ValueError("Invalid image format")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise ValueError("Image size exceeds 1 MB")

    return file
