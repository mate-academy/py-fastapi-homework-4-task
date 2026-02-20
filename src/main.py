import inspect

from fastapi import FastAPI, status, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from routes import (
    movie_router,
    accounts_router,
    profiles_router
)

app = FastAPI(
    title="Movies homework",
    description="Description of project"
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """
    Custom handler for RequestValidationError to properly serialize
    non-JSON-serializable objects within the error details.
    Це обробляє як UploadFile, так і ValueError об'єкти, які можуть бути
    вбудовані в деталі помилки Pydantic.
    """
    errors_to_json = []

    def make_serializable(obj):
        """
        Рекурсивна функція для перетворення несеріалізованих об'єктів
        на JSON-сумісні формати.
        """
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        if isinstance(obj, (list, tuple)):
            return [make_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {make_serializable(k): make_serializable(v) for k, v in obj.items()}

        if isinstance(obj, UploadFile):
            return {
                "filename": obj.filename,
                "content_type": obj.content_type,
                "size": obj.size,
                "detail": "UploadFile object (replaced for serialization)"
            }
        if isinstance(obj, Exception):
            return f"{obj.__class__.__name__}: {str(obj)}"
        if inspect.isclass(obj):
            return str(obj)

        try:
            return str(obj)
        except Exception:
            return f"<Unserializeble object {type(obj).__name__}>"

    for error in exc.errors():
        copied_error = error.copy()

        for key, value in copied_error.items():
            copied_error[key] = make_serializable(value)

        errors_to_json.append(copied_error)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors_to_json},
    )

api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(profiles_router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"])
app.include_router(movie_router, prefix=f"{api_version_prefix}/theater", tags=["theater"])
