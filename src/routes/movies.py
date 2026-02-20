from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config.dependencies import get_db
from database import (
    ActorModel,
    CountryModel,
    GenreModel,
    LanguageModel,
    MovieModel,
)
from schemas.movies import (
    MovieCreateSchema,
    MovieDetailSchema,
    MovieListItemSchema,
    MovieListResponseSchema,
    MovieUpdateSchema,
)

router = APIRouter(prefix="/movies", tags=["movies"])


def _page_link(page: int, per_page: int) -> str:
    # Tests expect EXACT format:
    # "/api/v1/theater/movies/?page=2&per_page=5"
    return f"/api/v1/theater/movies/?page={page}&per_page={per_page}"


async def _get_or_create_country(db: AsyncSession, code: str) -> CountryModel:
    country = await db.scalar(select(CountryModel).where(CountryModel.code == code))
    if country:
        return country
    # Name is not used in tests, but keep something sane.
    country = CountryModel(code=code, name=code)
    db.add(country)
    await db.flush()
    return country


async def _get_or_create_genres(db: AsyncSession, names: List[str]) -> List[GenreModel]:
    result: List[GenreModel] = []
    for genre_name in names:
        genre = await db.scalar(select(GenreModel).where(GenreModel.name == genre_name))
        if not genre:
            genre = GenreModel(name=genre_name)
            db.add(genre)
            await db.flush()
        result.append(genre)
    return result


async def _get_or_create_actors(db: AsyncSession, full_names: List[str]) -> List[ActorModel]:
    result: List[ActorModel] = []
    for full_name in full_names:
        actor = await db.scalar(select(ActorModel).where(ActorModel.full_name == full_name))
        if not actor:
            actor = ActorModel(full_name=full_name)
            db.add(actor)
            await db.flush()
        result.append(actor)
    return result


async def _get_or_create_languages(db: AsyncSession, names: List[str]) -> List[LanguageModel]:
    result: List[LanguageModel] = []
    for language_name in names:
        language = await db.scalar(select(LanguageModel).where(LanguageModel.name == language_name))
        if not language:
            language = LanguageModel(name=language_name)
            db.add(language)
            await db.flush()
        result.append(language)
    return result


def _to_list_item(movie: MovieModel) -> MovieListItemSchema:
    return MovieListItemSchema(
        id=movie.id,
        name=movie.name,
        date=movie.date,
        score=float(movie.score),
        overview=movie.overview,
        status=movie.status,
        budget=float(movie.budget),
        revenue=float(movie.revenue),
        country=movie.country.code if movie.country else "",
    )


def _to_detail(movie: MovieModel) -> MovieDetailSchema:
    return MovieDetailSchema(
        id=movie.id,
        name=movie.name,
        date=movie.date,
        score=float(movie.score),
        overview=movie.overview,
        status=movie.status,
        budget=float(movie.budget),
        revenue=float(movie.revenue),
        country=movie.country.code if movie.country else "",
        genres=[g.name for g in (movie.genres or [])],
        actors=[a.full_name for a in (movie.actors or [])],
        languages=[language.name for language in (movie.languages or [])],
    )


@router.get("/", response_model=MovieListResponseSchema)
async def get_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    total_items = await db.scalar(select(func.count(MovieModel.id)))
    total_items = int(total_items or 0)

    if total_items == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No movies found.")

    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page

    stmt = (
        select(MovieModel)
        .options(joinedload(MovieModel.country))
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    movies = (await db.execute(stmt)).scalars().all()

    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    if page > 1 and page <= total_pages:
        prev_page = _page_link(page - 1, per_page)
    if page < total_pages:
        next_page = _page_link(page + 1, per_page)

    return MovieListResponseSchema(
        total_items=total_items,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
        movies=[_to_list_item(m) for m in movies],
    )


@router.get("/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie_by_id(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    stmt = (
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
    )
    movie = (await db.execute(stmt)).scalars().first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    return _to_detail(movie)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=MovieDetailSchema)
async def create_movie(
    data: MovieCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    # Duplicate check: same name + date => 409
    dup_stmt = select(MovieModel).where(MovieModel.name == data.name, MovieModel.date == data.date)
    duplicate = (await db.execute(dup_stmt)).scalars().first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie with the same name and date already exists.",
        )

    country = await _get_or_create_country(db, data.country)
    genres = await _get_or_create_genres(db, data.genres)
    actors = await _get_or_create_actors(db, data.actors)
    languages = await _get_or_create_languages(db, data.languages)

    movie = MovieModel(
        name=data.name,
        date=data.date,
        score=data.score,
        overview=data.overview,
        status=data.status,
        budget=data.budget,
        revenue=data.revenue,
        country_id=country.id,
    )
    db.add(movie)
    await db.flush()

    movie.genres = genres
    movie.actors = actors
    movie.languages = languages

    await db.commit()
    await db.refresh(movie)

    stmt = (
        select(MovieModel)
        .where(MovieModel.id == movie.id)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
    )
    movie_full = (await db.execute(stmt)).scalars().first()
    return _to_detail(movie_full if movie_full else movie)


@router.patch("/{movie_id}/")
async def update_movie(
    movie_id: int,
    data: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
            joinedload(MovieModel.country),
        )
    )
    movie = (await db.execute(stmt)).scalars().first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    if data.name is not None:
        movie.name = data.name
    if data.date is not None:
        movie.date = data.date
    if data.score is not None:
        movie.score = data.score
    if data.overview is not None:
        movie.overview = data.overview
    if data.status is not None:
        movie.status = data.status
    if data.budget is not None:
        movie.budget = data.budget
    if data.revenue is not None:
        movie.revenue = data.revenue

    if data.country is not None:
        country = await _get_or_create_country(db, data.country)
        movie.country_id = country.id

    if data.genres is not None:
        movie.genres = await _get_or_create_genres(db, data.genres)
    if data.actors is not None:
        movie.actors = await _get_or_create_actors(db, data.actors)
    if data.languages is not None:
        movie.languages = await _get_or_create_languages(db, data.languages)

    await db.commit()
    return {"detail": "Movie updated successfully."}


@router.delete("/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    movie = await db.scalar(select(MovieModel).where(MovieModel.id == movie_id))
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    await db.delete(movie)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
