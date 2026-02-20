"""
Pydantic schemas for Movies API.

The integration tests import these names from `schemas.movies`:

- MovieListItemSchema
- MovieListResponseSchema
- MovieDetailSchema
- MovieCreateSchema
- MovieUpdateSchema
"""

from __future__ import annotations

from datetime import date as dt_date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MovieListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: dt_date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: str


class MovieListResponseSchema(BaseModel):
    total_items: int
    total_pages: int
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    movies: List[MovieListItemSchema]


class MovieDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: dt_date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: str
    genres: List[str]
    actors: List[str]
    languages: List[str]


class MovieCreateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    date: dt_date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: str = Field(..., min_length=1)
    genres: List[str]
    actors: List[str]
    languages: List[str]


class MovieUpdateSchema(BaseModel):
    # PATCH: all fields optional
    name: Optional[str] = Field(default=None, min_length=1)
    date: Optional[dt_date] = None
    score: Optional[float] = None
    overview: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[float] = None
    revenue: Optional[float] = None
    country: Optional[str] = Field(default=None, min_length=1)
    genres: Optional[List[str]] = None
    actors: Optional[List[str]] = None
    languages: Optional[List[str]] = None
