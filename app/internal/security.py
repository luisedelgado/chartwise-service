from fastapi import HTTPException, status
from pydantic import BaseModel

AUTH_TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

STORE_TOKENS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="One or more store token headers are missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

class Token(BaseModel):
    auth_token: str
    token_type: str
    expiration_timestamp: str
