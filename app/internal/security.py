import datetime, jwt, logging, os, uuid

from datetime import datetime, timedelta, timezone
from fastapi import Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Annotated, Union

from .model import SessionRefreshData

SECRET_KEY = os.environ.get('FASTAPI_JWT_SECRET')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class User(BaseModel):
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
logging.getLogger('passlib').setLevel(logging.ERROR)

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

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_entity(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_entity(fake_db, username: str, password: str):
    user = get_entity(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def access_token_is_valid(access_token: str) -> bool:
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return False
        token_data = TokenData(username=username)
    except:
        return False
    user = get_entity(users_db, username=token_data.username)
    if user is None or user.disabled is True:
        return False

    # Check that token hasn't expired
    token_expiration_date = datetime.fromtimestamp(payload.get("exp"),
                                                   tz=timezone.utc)
    return (token_expiration_date > datetime.now(timezone.utc))

async def get_current_auth_entity(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_entity(users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_auth_entity(
    current_auth_entity: Annotated[User, Depends(get_current_auth_entity)],
):
    if current_auth_entity.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_auth_entity

"""
Refreshes the user's auth token for a continued session experience.

Arguments:
user – The user for whom to refresh the session.
response  – the model with which to build the API response.
"""
def update_auth_token_for_entity(user: User, response: Response):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    response.delete_cookie("authorization")
    response.set_cookie(key="authorization",
                        value=access_token,
                        httponly=True,
                        secure=True,
                        samesite="none")
    return Token(access_token=access_token, token_type="bearer")

"""
Validates the incoming session cookies.

Arguments:
user – the user for whom to refresh the current session.
response – the response object where we can update cookies.
current_session_id – the session_id cookie to be validated, if exists.
"""
async def refresh_session(user: User,
                          response: Response,
                          session_id: Annotated[Union[str, None], Cookie()] = None) -> SessionRefreshData | None:
    try:
        token = update_auth_token_for_entity(user, response)

        if session_id is not None:
            return SessionRefreshData(session_id=session_id,
                                      auth_token=token)

        new_session_id = uuid.uuid1()
        response.delete_cookie("session_id")
        response.set_cookie(key="session_id",
                    value=new_session_id,
                    httponly=True,
                    secure=True,
                    samesite="none")
        return SessionRefreshData(session_id=new_session_id,
                                  auth_token=token)
    except Exception as e:
        raise Exception(str(e))
