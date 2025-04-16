from fastapi import HTTPException, status
from pydantic import BaseModel

SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Session token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

class Token(BaseModel):
    session_token: str
    token_type: str
    expiration_timestamp: str
