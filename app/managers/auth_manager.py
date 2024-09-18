import jwt, logging, os, requests

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Request, Response
from passlib.context import CryptContext
from portkey_ai import PORTKEY_GATEWAY_URL
from typing import Tuple

from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..internal.dependency_container import dependency_container
from ..internal.security import Token
from ..internal.utilities.datetime_handler import DATE_TIME_FORMAT

class AuthManager:

    APP_COOKIE_DOMAIN = ("chartwise.ai" if os.environ.get("ENVIRONMENT") == "prod"
                         else None)
    SECRET_KEY = os.environ.get('FASTAPI_JWT_SECRET')
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 120

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

    def create_access_token(self, user_id: str) -> Tuple[str, str]:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Couldn't make a user out of the incoming ids",
                headers={"WWW-Authenticate": "Bearer"},
            )

        data = {"sub": user_id}
        to_encode = data.copy()
        expiration_delta = timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        expiration_time = datetime.now(timezone.utc) + expiration_delta
        to_encode.update({"exp": expiration_time})

        formatted_expiration_time = expiration_time.strftime(DATE_TIME_FORMAT)
        return (jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM), formatted_expiration_time)

    def access_token_is_valid(self, access_token: str) -> bool:
        try:
            payload = jwt.decode(access_token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id == None:
                return False

            # Check that token hasn't expired
            token_expiration_date = datetime.fromtimestamp(payload.get("exp"),
                                                           tz=timezone.utc)
            return (token_expiration_date > datetime.now(timezone.utc))
        except:
            return False

    async def refresh_session(self,
                              user_id: str,
                              request: Request,
                              response: Response,
                              datastore_access_token: str = None,
                              datastore_refresh_token: str = None) -> Token:
        try:
            access_token, expiration_timestamp = self.create_access_token(user_id)
            response.set_cookie(key="authorization",
                                value=access_token,
                                domain=self.APP_COOKIE_DOMAIN,
                                httponly=True,
                                secure=True,
                                samesite="none")

            # We are being sent new datastore tokens. Let's update cookies.
            if len(datastore_access_token or '') > 0 and len(datastore_refresh_token or '') > 0:
                response.set_cookie(key="datastore_access_token",
                                    value=datastore_access_token,
                                    domain=self.APP_COOKIE_DOMAIN,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
                response.set_cookie(key="datastore_refresh_token",
                                    value=datastore_refresh_token,
                                    domain=self.APP_COOKIE_DOMAIN,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
            # If we have datastore tokens in cookies, let's refresh them.
            elif "datastore_access_token" in request.cookies and "datastore_refresh_token" in request.cookies:
                supabase_client_factory = dependency_container.get_supabase_client_factory()
                supabase_client: SupabaseBaseClass = supabase_client_factory.supabase_user_client(access_token=request.cookies['datastore_access_token'],
                                                                                                  refresh_token=request.cookies['datastore_refresh_token'])
                refresh_session_response = supabase_client.refresh_session().dict()
                assert refresh_session_response['user']['role'] == 'authenticated'

                datastore_access_token = refresh_session_response['session']['access_token']
                datastore_refresh_token = refresh_session_response['session']['refresh_token']
                response.set_cookie(key="datastore_access_token",
                                    value=datastore_access_token,
                                    domain=self.APP_COOKIE_DOMAIN,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
                response.set_cookie(key="datastore_refresh_token",
                                    value=datastore_refresh_token,
                                    domain=self.APP_COOKIE_DOMAIN,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")
            else:
                datastore_access_token = None
                datastore_refresh_token = None

            return Token(access_token=access_token,
                         token_type="bearer",
                         expiration_timestamp=expiration_timestamp)
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
