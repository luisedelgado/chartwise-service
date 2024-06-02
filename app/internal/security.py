import datetime, jwt, logging, os

from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Annotated, Union

SECRET_KEY = os.environ.get('FASTAPI_JWT_SECRET')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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
    "testonly": {
        "username": "testonly",
        "full_name": "testonly",
        "email": "testonly",
        "hashed_password": "$2b$12$DRj2D.Tsy5gs9SpLVhxAiuGli3O2SJUE2o7W8X.fuQY63szNg8kbK",
        "disabled": False,
    }
}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
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
    user = get_user(users_db, username=token_data.username)
    if user is None or user.disabled is True:
        return False

    # Check that token hasn't expired
    token_expiration_date = datetime.fromtimestamp(payload.get("exp"),
                                                   tz=timezone.utc)
    return (token_expiration_date > datetime.now(timezone.utc))

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
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
    user = get_user(users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
