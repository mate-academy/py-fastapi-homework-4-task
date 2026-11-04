from routes.accounts import router as accounts_router
from routes.movies import router as movie_router
from routes.profiles import router as profiles_router

__all__ = [
    "accounts_router",
    "movie_router",
    "profiles_router",
]
