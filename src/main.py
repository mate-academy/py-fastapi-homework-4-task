from fastapi import FastAPI, UploadFile, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from routes import movie_router, accounts_router, profiles_router

app = FastAPI(title="Movies homework", description="Description of project")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()

    for error in errors:
        if "input" in error:
            error.pop("input")

        if "ctx" in error and "error" in error["ctx"]:
            ctx_error = error["ctx"]["error"]
            if isinstance(ctx_error, Exception):
                error["ctx"]["error"] = str(ctx_error)

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


api_version_prefix = "/api/v1"

app.include_router(
    accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"]
)
app.include_router(
    profiles_router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"]
)
app.include_router(
    movie_router, prefix=f"{api_version_prefix}/theater", tags=["theater"]
)
