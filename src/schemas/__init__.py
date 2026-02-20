"""
Schemas package.

IMPORTANT:
This module is executed whenever any submodule like `schemas.movies` is imported.
So it must NOT import names that don't exist, otherwise you'll get ImportError
even if you import `schemas.movies` directly.
"""

# Accounts
from .accounts import (
    MessageResponseSchema,
    PasswordResetCompleteRequestSchema,
    PasswordResetRequestSchema,
    TokenResponseSchema,
    UserActivationRequestSchema,
    UserLoginRequestSchema,
    UserRegisterRequestSchema,
)

# Profiles
from .profiles import ProfileCreateSchema, ProfileResponseSchema

# Movies
from .movies import (
    MovieCreateSchema,
    MovieDetailSchema,
    MovieListItemSchema,
    MovieListResponseSchema,
    MovieUpdateSchema,
)

__all__ = [
    # Accounts
    "MessageResponseSchema",
    "PasswordResetCompleteRequestSchema",
    "PasswordResetRequestSchema",
    "TokenResponseSchema",
    "UserActivationRequestSchema",
    "UserLoginRequestSchema",
    "UserRegisterRequestSchema",
    # Profiles
    "ProfileCreateSchema",
    "ProfileResponseSchema",
    # Movies
    "MovieCreateSchema",
    "MovieDetailSchema",
    "MovieListItemSchema",
    "MovieListResponseSchema",
    "MovieUpdateSchema",
]
