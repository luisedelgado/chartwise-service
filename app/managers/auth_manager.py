import jwt, logging, os, requests, uuid

from datetime import datetime, timedelta, timezone
from fastapi import Cookie, HTTPException, status, Request, Response
from passlib.context import CryptContext
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
from typing import Union

from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ..internal.security import Token

class AuthManager:

    SECRET_KEY = os.environ.get('FASTAPI_JWT_SECRET')
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    def __init__(self):
        self._pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        logging.getLogger('passlib').setLevel(logging.ERROR)

    # Authentication

    def authenticate_datastore_user(self,
                                    user_id: str,
                                    supabase_client: SupabaseBaseClass) -> bool:
        try:
            response = supabase_client.get_user().dict()
            return response['user']['id'] == user_id
        except Exception as e:
            raise Exception(str(e))

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
            user_id: str = payload.get("sub")
            if user_id is None:
                return False
        except:
            return False

        # Check that token hasn't expired
        token_expiration_date = datetime.fromtimestamp(payload.get("exp"),
                                                       tz=timezone.utc)
        return (token_expiration_date > datetime.now(timezone.utc))

    def update_auth_token_for_entity(self, user_id: str, response: Response) -> Token:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Couldn't make a user out of the incoming ids",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={"sub": user_id}, expires_delta=access_token_expires
        )
        response.set_cookie(key="authorization",
                            value=access_token,
                            httponly=True,
                            secure=True,
                            samesite="none")
        return Token(access_token=access_token, token_type="bearer")

    async def refresh_session(self,
                              user_id: str,
                              request: Request,
                              response: Response,
                              supabase_client_factory: SupabaseFactoryBaseClass,
                              datastore_access_token: str = None,
                              datastore_refresh_token: str = None) -> Token:
        try:
            auth_token = self.update_auth_token_for_entity(user_id, response)

            # We are being sent new datastore tokens. Let's update cookies.
            if len(datastore_access_token or '') > 0 and len(datastore_refresh_token or '') > 0:
                response.set_cookie(key="datastore_access_token",
                                    value=datastore_access_token,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
                response.set_cookie(key="datastore_refresh_token",
                                    value=datastore_refresh_token,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
            # If we have datastore tokens in cookies, let's refresh them.
            elif "datastore_access_token" in request.cookies and "datastore_refresh_token" in request.cookies:
                supabase_client: SupabaseBaseClass = supabase_client_factory.supabase_user_client(access_token=request.cookies['datastore_access_token'],
                                                                                                  refresh_token=request.cookies['datastore_refresh_token'])
                refresh_session_response = supabase_client.refresh_session().dict()
                assert refresh_session_response['user']['role'] == 'authenticated'

                datastore_access_token = refresh_session_response['session']['access_token']
                datastore_refresh_token = refresh_session_response['session']['refresh_token']
                response.set_cookie(key="datastore_access_token",
                                    value=datastore_access_token,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
                response.set_cookie(key="datastore_refresh_token",
                                    value=datastore_refresh_token,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
            else:
                datastore_access_token = None
                datastore_refresh_token = None

            return auth_token
        except Exception as e:
            raise HTTPException(detail=str(e), status_code=status.HTTP_401_UNAUTHORIZED)

    def logout(self, response: Response):
        response.delete_cookie("authorization")
        response.delete_cookie("session_id")
        response.delete_cookie("datastore_access_token")
        response.delete_cookie("datastore_refresh_token")

    # Portkey

    def get_monitoring_proxy_url(self) -> str:
        return PORTKEY_GATEWAY_URL

    def is_monitoring_proxy_reachable(self) -> bool:
        try:
            return requests.get(self.get_monitoring_proxy_url()).status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
        except:
            return False

    def create_monitoring_proxy_config(self, llm_model, cache_max_age = None):
        config = {
            "provider": "openai",
            "virtual_key": os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
            "retry": {
                "attempts": 2,
            },
            "override_params": {
                "model": llm_model,
                "temperature": 0,
            }
        }
        if cache_max_age is not None:
            config["cache"] = {
                "mode": "semantic",
                "max_age": cache_max_age,
            }
        return config

    def create_monitoring_proxy_headers(self, **kwargs):
        caching_shard_key = None if "caching_shard_key" not in kwargs else kwargs["caching_shard_key"]
        cache_max_age = None if "cache_max_age" not in kwargs else kwargs["cache_max_age"]
        llm_model = None if "llm_model" not in kwargs else kwargs["llm_model"]
        metadata = None if "metadata" not in kwargs else kwargs["metadata"]

        if cache_max_age is not None and caching_shard_key is not None:
            monitoring_proxy_config = self.create_monitoring_proxy_config(cache_max_age=cache_max_age,
                                                                          llm_model=llm_model)
            return createHeaders(trace_id=uuid.uuid4(),
                                 api_key=os.environ.get("PORTKEY_API_KEY"),
                                 config=monitoring_proxy_config,
                                 cache_namespace=caching_shard_key,
                                 metadata=metadata)

        monitoring_proxy_config = self.create_monitoring_proxy_config(llm_model=llm_model)
        return createHeaders(trace_id=uuid.uuid4(),
                             api_key=os.environ.get("PORTKEY_API_KEY"),
                             config=monitoring_proxy_config,
                             metadata=metadata)
