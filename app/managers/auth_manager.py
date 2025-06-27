import jwt, logging, os

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Response
from passlib.context import CryptContext
from typing import Tuple

from ..internal.schemas import PROD_ENVIRONMENT, STAGING_ENVIRONMENT
from ..internal.security.security_schema import Token
from ..internal.utilities.datetime_handler import DATE_TIME_FORMAT
from ..internal.session_container import session_container
from ..dependencies.dependency_container import dependency_container

class AuthManager:

    SESSION_TOKEN_KEY = "session_token"
    SESSION_ID_KEY = "session_id"
    ENVIRONMENT = os.environ.get("ENVIRONMENT")
    APP_COOKIE_DOMAIN = (".chartwise.ai" if (os.environ.get("ENVIRONMENT") == PROD_ENVIRONMENT
                         or os.environ.get("ENVIRONMENT") == STAGING_ENVIRONMENT) else None)
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 120

    def __init__(self):
        secret_manager = dependency_container.inject_aws_secret_manager_client()
        secret_id = os.environ.get("SESSION_TOKEN_JWT_SECRET_NAME")
        assert secret_id is not None, "Nullable JWT Secret, secret name"
        secret_data = secret_manager.get_secret(
            secret_id=secret_id,
            resend_client=dependency_container.inject_resend_client(),
        )
        assert type(secret_data) == dict, "Unexpected data type"
        self.secret_key = secret_data.get('secret')
        self._pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        logging.getLogger('passlib').setLevel(logging.ERROR)

    # Authentication

    def create_session_token(
        self,
        user_id: str,
    ) -> Tuple[str, str]:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Couldn't make a user out of the incoming ids",
                headers={"WWW-Authenticate": "Bearer"},
            )

        cls = type(self)
        expiration_delta = timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        expiration_time = datetime.now(timezone.utc) + expiration_delta

        data = {"sub": user_id}
        to_encode: dict = data.copy()
        to_encode.update({"exp": expiration_time})

        formatted_expiration_time = expiration_time.strftime(DATE_TIME_FORMAT)
        return (
            jwt.encode(
                to_encode,
                self.secret_key,
                algorithm=cls.ALGORITHM
            ),
            formatted_expiration_time
        )

    def session_token_is_valid(
        self,
        access_token: str,
    ) -> bool:
        try:
            token_data: dict = self.extract_data_from_token(access_token)
            user_id = token_data.get("user_id")
            if user_id == None or len(user_id) == 0:
                return False

            # Check that token hasn't expired
            exp = token_data.get("exp")
            assert type(exp) == int, "Unexpected exp datatype"
            token_expiration_date = datetime.fromtimestamp(
                exp,
                tz=timezone.utc
            )
            return (token_expiration_date > datetime.now(timezone.utc))
        except Exception:
            return False

    def extract_data_from_token(
        self,
        access_token: str,
    ) -> dict:
        try:
            payload = jwt.decode(
                jwt=access_token,
                key=self.secret_key,
                algorithms=[type(self).ALGORITHM]
            )
            exp: float = payload.get("exp")
            user_id: str = payload.get("sub")

            if len(user_id or '') == 0:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: user ID not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return {
                "user_id": user_id,
                "exp": exp
            }
        except Exception as e:
            raise RuntimeError(e) from e

    async def refresh_session(
        self,
        user_id: str,
        response: Response,
        session_id: str | None,
    ) -> Token:
        try:
            session_container.user_id = user_id
            session_container.session_id = session_id
            session_token, expiration_timestamp = self.create_session_token(user_id)
            cls = type(self)
            response.set_cookie(
                key=cls.SESSION_TOKEN_KEY,
                value=session_token,
                domain=cls.APP_COOKIE_DOMAIN,
                httponly=True,
                secure=True,
                samesite="none"
            )

            return Token(
                session_token=session_token,
                token_type="bearer",
                expiration_timestamp=expiration_timestamp
            )
        except Exception as e:
            raise HTTPException(
                detail=str(e),
                status_code=status.HTTP_401_UNAUTHORIZED
            )

    def logout(
        self,
        response: Response,
    ):
        cls = type(self)
        response.delete_cookie(cls.SESSION_TOKEN_KEY)
        response.delete_cookie(cls.SESSION_ID_KEY)
