from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Union

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="token")

AUTH_TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

DATASTORE_TOKENS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="One or more datastore tokens are missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Union[str, None] = None

class User(BaseModel):
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str

users_db = {
    "luisdelgado": {
        "username": "luisdelgado",
        "full_name": "Luis Delgado",
        "email": "luis.e.delgado24@gmail.com",
        "hashed_password": "$2b$12$vUVd7oQPSkfr3xq2KzyAieUWjWwDOCDsKtPK/PPouqPtMHE1h66SO",
        "disabled": False,
    },
    "danieldaza": {
        "username": "danieldaza",
        "full_name": "Daniel Daza",
        "email": "danieldaza91@gmail.com",
        "hashed_password": "$2b$12$xij/dxNEivS1Slp7lex11.Lyu/M7IDdXVNDRHud9JzGs/ndRbE5ce",
        "disabled": False
    },
}
