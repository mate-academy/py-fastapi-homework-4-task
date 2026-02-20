from pydantic import BaseModel
from src.database.models.accounts import GenderEnum

class ProfileRequestSchema(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum  # Використовуємо GenderEnum для коректної валідації

    class Config:
        orm_mode = True

class ProfileResponseSchema(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum  # Замість str використовуємо GenderEnum

    class Config:
        orm_mode = True
