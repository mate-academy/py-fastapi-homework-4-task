from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def validate_api_key(api_key: str = Security(api_key_header)):

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is missing"
        )

    decoded_auth_header = api_key.split()
    if decoded_auth_header[0] != "Bearer" or len(decoded_auth_header) != 2:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'")

    return api_key
