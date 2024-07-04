import jwt, logging, os, requests, uuid

from datetime import datetime, timedelta, timezone
from fastapi import Cookie, Depends, HTTPException, status, Response
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
from supabase import create_client, Client
from typing import Annotated, Union

from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import SessionRefreshData
from ...internal.security import OAUTH2_SCHEME, Token, TokenData, User, UserInDB, users_db

class AuthManager(AuthManagerBaseClass):

    SECRET_KEY = os.environ.get('FASTAPI_JWT_SECRET')
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    def __init__(self):
        self._pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        logging.getLogger('passlib').setLevel(logging.ERROR)

    # Authentication

    def verify_password(self, plain_password, hashed_password):
        return self._pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return self._pwd_context.hash(password)

    def get_entity(self, db, username: str):
        if username in db:
            user_dict = db[username]
            return UserInDB(**user_dict)

    def authenticate_entity(self, fake_db, username: str, password: str):
        user = self.get_entity(fake_db, username)
        if not user:
            return False
        if not self.verify_password(password, user.hashed_password):
            return False
        return user

    def create_access_token(self,
                            data: dict,
                            expires_delta: Union[timedelta, None] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def access_token_is_valid(self, access_token: str) -> bool:
        try:
            payload = jwt.decode(access_token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return False
            token_data = TokenData(username=username)
        except:
            return False
        user = self.get_entity(users_db, username=token_data.username)
        if user is None or user.disabled is True:
            return False

        # Check that token hasn't expired
        token_expiration_date = datetime.fromtimestamp(payload.get("exp"),
                                                    tz=timezone.utc)
        return (token_expiration_date > datetime.now(timezone.utc))

    async def get_current_auth_entity(self, token: Annotated[str, Depends(OAUTH2_SCHEME)]):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except InvalidTokenError:
            raise credentials_exception
        user = self.get_entity(users_db, username=token_data.username)
        if user is None:
            raise credentials_exception
        return user

    async def get_current_active_auth_entity(self,
                                             current_auth_entity: Annotated[User, Depends(get_current_auth_entity)]):
        if current_auth_entity.disabled:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_auth_entity

    def update_auth_token_for_entity(self, user: User, response: Response):
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        response.delete_cookie("authorization")
        response.set_cookie(key="authorization",
                            value=access_token,
                            httponly=True,
                            secure=True,
                            samesite="none")
        return Token(access_token=access_token, token_type="bearer")

    async def refresh_session(self,
                              user: User,
                              response: Response,
                              session_id: Annotated[Union[str, None], Cookie()] = None) -> SessionRefreshData | None:
        try:
            token = self.update_auth_token_for_entity(user, response)

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

    def logout(self, response: Response):
        response.delete_cookie("authorization")
        response.delete_cookie("session_id")

    # Supabase

    def datastore_user_instance(self, access_token, refresh_token) -> Client:
        key: str = os.environ.get("SUPABASE_ANON_KEY")
        url: str = os.environ.get("SUPABASE_URL")
        supabase: Client = create_client(url, key)
        supabase.auth.set_session(access_token=access_token,
                                  refresh_token=refresh_token)
        return supabase

    def datastore_admin_instance(self) -> Client:
        key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        url: str = os.environ.get("SUPABASE_URL")
        return create_client(url, key)

    # Portkey

    def get_monitoring_proxy_url(self) -> str:
        return PORTKEY_GATEWAY_URL

    def is_monitoring_proxy_reachable(self) -> bool:
        try:
            return requests.get(self.get_monitoring_proxy_url()).status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
        except:
            return False

    def create_monitoring_proxy_config(self, cache_max_age, llm_model):
        return {
            "provider": "openai",
            "virtual_key": os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
            "cache": {
                "mode": "semantic",
                "max_age": cache_max_age,
            },
            "retry": {
                "attempts": 2,
            },
            "override_params": {
                "model": llm_model,
                "temperature": 0,
            }
        }

    def create_monitoring_proxy_headers(self, **kwargs):
        caching_shard_key = None if "caching_shard_key" not in kwargs else kwargs["caching_shard_key"]
        cache_max_age = None if "cache_max_age" not in kwargs else kwargs["cache_max_age"]
        llm_model = None if "llm_model" not in kwargs else kwargs["llm_model"]
        metadata = None if "metadata" not in kwargs else kwargs["metadata"]
        return createHeaders(trace_id=uuid.uuid4(),
                            api_key=os.environ.get("PORTKEY_API_KEY"),
                            config=self.create_monitoring_proxy_config(cache_max_age=cache_max_age,
                                                                       llm_model=llm_model),
                            cache_namespace=caching_shard_key,
                            metadata=metadata)
