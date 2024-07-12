from datetime import timedelta

from fastapi import Request, Response
from supabase import Client
from typing import Union

from .fake_supabase_client import FakeSupabaseClient
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.security import Token

class FakeAuthManager(AuthManagerBaseClass):

    FAKE_SESSION_ID = "8fc1b533-304e-4a33-98ba-541fdd956c1f"
    FAKE_AUTH_TOKEN = "myRandomGibberish"
    FAKE_PASSWORD = "myPassword"
    FAKE_HASHED_PASSWORD = "myHashedPassword"
    FAKE_FULL_NAME = "John Doe"
    FAKE_USERNAME = "myfakeusername"
    FAKE_USER_ID = "ffc1b533-304e-4a33-98ba-541fdd956c1f"
    FAKE_EMAIL = "johndoe@fakeemail.fake"
    FAKE_DATASTORE_ACCESS_TOKEN = "fakeDatastoreAccessToken"
    FAKE_DATASTORE_REFRESH_TOKEN = "fakeDatastoreRefreshToken"

    auth_cookie: str = None
    fake_supabase_client: FakeSupabaseClient

    def __init__(self):
        self.fake_supabase_client = FakeSupabaseClient()

    # Authentication

    def authenticate_datastore_user(self,
                                    user_id: str,
                                    datastore_access_token: str,
                                    datastore_refresh_token: str) -> bool:
        return (user_id == self.FAKE_USER_ID and
                datastore_access_token == self.FAKE_DATASTORE_ACCESS_TOKEN and
                datastore_refresh_token == self.FAKE_DATASTORE_REFRESH_TOKEN)

    def create_access_token(self,
                            _: dict,
                            __: Union[timedelta, None] = None):
        return self.FAKE_AUTH_TOKEN

    def access_token_is_valid(self, access_token: str) -> bool:
        return self.auth_cookie == access_token

    def update_auth_token_for_entity(self, user_id: str, response: Response) -> Token:
        pass

    async def refresh_session(self,
                              user_id: str,
                              request: Request,
                              response: Response,
                              datastore_access_token: str = None,
                              datastore_refresh_token: str = None) -> Token:
        assert user_id == self.FAKE_USER_ID
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
        response.set_cookie(key="datastore_access_token",
                            value=self.FAKE_DATASTORE_ACCESS_TOKEN,
                            httponly=True,
                            secure=True,
                            samesite="none")
        response.set_cookie(key="datastore_refresh_token",
                            value=self.FAKE_DATASTORE_REFRESH_TOKEN,
                            httponly=True,
                            secure=True,
                            samesite="none")
        return Token(access_token=self.FAKE_AUTH_TOKEN, token_type="bearer")

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
        response.delete_cookie("datastore_access_token")
        response.delete_cookie("datastore_refresh_token")
