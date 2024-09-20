from fastapi import HTTPException, status
from pydantic import BaseModel

AUTH_TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

DATASTORE_TOKENS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="One or more datastore token headers are missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

class Token(BaseModel):
    access_token: str
    token_type: str
    expiration_timestamp: str
