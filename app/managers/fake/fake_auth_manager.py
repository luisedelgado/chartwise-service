from datetime import timedelta

from fastapi import Cookie, Depends, Response
from supabase import Client
from typing import Annotated, Union

from .fake_supabase_client import FakeSupabaseClient
from ...internal.model import SessionRefreshData
from ...internal.security import OAUTH2_SCHEME, Token, User, UserInDB
from ...api.auth_base_class import AuthManagerBaseClass


class FakeAuthManager(AuthManagerBaseClass):

    FAKE_SESSION_ID = "8fc1b533-304e-4a33-98ba-541fdd956c1f"
    FAKE_AUTH_TOKEN = "myRandomGibberish"
    FAKE_PASSWORD = "myPassword"
    FAKE_HASHED_PASSWORD = "myHashedPassword"
    FAKE_FULL_NAME = "John Doe"
    FAKE_USERNAME = "myfakeusername"
    FAKE_EMAIL = "johndoe@fakeemail.fake"
    FAKE_USER_IN_DB = UserInDB(username=FAKE_USERNAME,
                            email=FAKE_EMAIL,
                            full_name=FAKE_FULL_NAME,
                            hashed_password=FAKE_HASHED_PASSWORD,
                            disabled=False)

    auth_cookie: str = None
    fake_supabase_client: FakeSupabaseClient

    def __init__(self):
        self.fake_supabase_client = FakeSupabaseClient()

    # Authentication

    def verify_password(self, plain_password, hashed_password):
        pass

    def get_password_hash(self, password):
        pass

    def get_entity(self, db, username: str):
        pass

    def authenticate_entity(self, fake_db, username: str, password: str):
        if username != self.FAKE_USERNAME or password != self.FAKE_PASSWORD:
            return None
        return UserInDB(username=self.FAKE_USERNAME,
                        email=self.FAKE_EMAIL,
                        full_name=self.FAKE_FULL_NAME,
                        disabled=False,
                        hashed_password=self.FAKE_HASHED_PASSWORD)

    def create_access_token(self,
                            _: dict,
                            __: Union[timedelta, None] = None):
        return self.FAKE_AUTH_TOKEN

    def access_token_is_valid(self, access_token: str) -> bool:
        return self.auth_cookie == access_token

    async def get_current_auth_entity(self, _: Annotated[str, Depends(OAUTH2_SCHEME)]):
        return self.FAKE_USER_IN_DB

    async def get_current_active_auth_entity(self,
                                             _: Annotated[User, Depends(get_current_auth_entity)]):
        self.FAKE_USER_IN_DB

    def update_auth_token_for_entity(self, user: User, response: Response):
        pass

    async def refresh_session(self,
                              user: User,
                              response: Response,
                              session_id: Annotated[Union[str, None], Cookie()] = None) -> SessionRefreshData | None:
        response.set_cookie(key="session_id",
                        value=self.FAKE_SESSION_ID,
                        httponly=True,
                        secure=True,
                        samesite="none")

        response.set_cookie(key="authorization",
                        value=self.FAKE_AUTH_TOKEN,
                        httponly=True,
                        secure=True,
                        samesite="none")

        token = Token(access_token=self.FAKE_AUTH_TOKEN, token_type="bearer")
        return SessionRefreshData(session_id=self.FAKE_SESSION_ID,
                                  auth_token=token)

    def datastore_user_instance(self, access_token, refresh_token) -> Client:
        return self.fake_supabase_client

    def datastore_admin_instance(self) -> Client:
        return self.fake_supabase_client

    def get_monitoring_proxy_url(self) -> str:
        return ""

    def is_monitoring_proxy_reachable(self) -> bool:
        return False

    def create_monitoring_proxy_config(self, cache_max_age, llm_model):
        return {}

    def create_monitoring_proxy_headers(self, **kwargs):
        return {}

    def logout(self, response: Response):
        response.delete_cookie("authorization")
        response.delete_cookie("session_id")
