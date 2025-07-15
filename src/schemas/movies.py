from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from database.models.movies import MovieStatusEnum

movie_item_schema_example = {
    "id": 9933,
    "name": "The Swan Princess: A Royal Wedding",
    "date": "2020-07-20",
    "score": 70,
    "overview": "Princess Odette and Prince Derek are going to a wedding at Princess Mei Li and her beloved Chen. "
                "But evil forces are at stake and the wedding plans are tarnished and "
                "true love has difficult conditions."
}

movie_list_response_schema_example = {
    "movies": [
        movie_item_schema_example
    ],
    "prev_page": "/theater/movies/?page=1&per_page=1",
    "next_page": "/theater/movies/?page=3&per_page=1",
    "total_pages": 9933,
    "total_items": 9933
}

movie_create_schema_example = {
    "name": "New Movie",
    "date": "2025-01-01",
    "score": 85.5,
    "overview": "An amazing movie.",
    "status": "Released",
    "budget": 1000000.00,
    "revenue": 5000000.00,
    "country": "US",
    "genres": ["Action", "Adventure"],
    "actors": ["John Doe", "Jane Doe"],
    "languages": ["English", "French"]
}

language_schema_example = {
    "id": 1,
    "name": "English"
}

country_schema_example = {
    "id": 1,
    "code": "US",
    "name": "United States"
}

genre_schema_example = {
    "id": 1,
    "genre": "Comedy"
}

actor_schema_example = {
    "id": 1,
    "name": "JimmyFallon"
}

movie_detail_schema_example = {
    **movie_item_schema_example,
    "status": "Released",
    "budget": 1000000.00,
    "revenue": 5000000.00,
    "actors": [actor_schema_example],
    "country": country_schema_example,
    "genres": [genre_schema_example],
    "languages": [language_schema_example]
}

movie_update_schema_example = {
    "name": "Update Movie",
    "date": "2025-01-01",
    "score": 85.5,
    "overview": "An amazing movie.",
    "status": "Released",
    "budget": 1000000.00,
    "revenue": 5000000.00,
}


class LanguageSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                language_schema_example
            ]
        }
    }


class CountrySchema(BaseModel):
    id: int
    code: str
    name: Optional[str]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                country_schema_example
            ]
        }
    }


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                genre_schema_example
            ]
        }
    }


class ActorSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                actor_schema_example
            ]
        }
    }


class MovieBaseSchema(BaseModel):
    name: str = Field(..., max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: MovieStatusEnum
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)

    model_config = {
        "from_attributes": True
    }

    @field_validator("date")
    @classmethod
    def validate_date(cls, value):
        current_year = datetime.now().year
        if value.year > current_year + 1:
            raise ValueError(f"The year in 'date' cannot be greater than {current_year + 1}.")
        return value


class MovieDetailSchema(MovieBaseSchema):
    id: int
    country: CountrySchema
    genres: List[GenreSchema]
    actors: List[ActorSchema]
    languages: List[LanguageSchema]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_detail_schema_example
            ]
        }
    }


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_item_schema_example
            ]
        }
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_list_response_schema_example
            ]
        }
    }


class MovieCreateSchema(BaseModel):
    name: str
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: MovieStatusEnum
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: str
    genres: List[str]
    actors: List[str]
    languages: List[str]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_create_schema_example
            ]
        }
    }

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.upper()

    @field_validator("genres", "actors", "languages", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: List[str]) -> List[str]:
        return [item.title() for item in value]


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[MovieStatusEnum] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_update_schema_example
            ]
        }
    }
