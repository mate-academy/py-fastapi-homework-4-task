from datetime import date

from pydantic import BaseModel, ConfigDict


class ProfileCreateResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str
