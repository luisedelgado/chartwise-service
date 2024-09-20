import jwt, logging, os

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Response
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

    def authenticate_store_user(self,
                                username: str,
                                password: str) -> bool:
        try:
            supabase_client: SupabaseBaseClass = dependency_container.inject_supabase_client_factory().supabase_admin_client()
            signin_response = supabase_client.auth.sign_in_with_password({"email": username, "password": password})

            assert "user" in signin_response, "Failed to authenticate user."
            return signin_response['user']['id']
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
                              response: Response) -> Token:
        try:
            access_token, expiration_timestamp = self.create_access_token(user_id)
            response.set_cookie(key="authorization",
                                value=access_token,
                                domain=self.APP_COOKIE_DOMAIN,
                                httponly=True,
                                secure=True,
                                samesite="none")

            return Token(access_token=access_token,
                         token_type="bearer",
                         expiration_timestamp=expiration_timestamp)
        except Exception as e:
            raise HTTPException(detail=str(e), status_code=status.HTTP_401_UNAUTHORIZED)

    def logout(self, response: Response):
        response.delete_cookie("authorization")
        response.delete_cookie("session_id")
