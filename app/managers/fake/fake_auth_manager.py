from datetime import timedelta

from fastapi import Cookie, Depends, Response
from supabase import Client
from typing import Annotated, Union

from ...internal.model import SessionRefreshData
from ...internal.security import OAUTH2_SCHEME, Token, User, UserInDB
from ...api.auth_base_class import AuthManagerBaseClass

FAKE_SESSION_ID = "8fc1b533-304e-4a33-98ba-541fdd956c1f"
FAKE_ACCESS_TOKEN = "myRandomGibberish"
FAKE_HASHED_PASSWORD = "myHashedPassword"
FAKE_USER_IN_DB = UserInDB(username="myfakeusername",
                           email="johndoe@fakeemail.fake",
                           full_name="John Doe",
                           hashed_password=FAKE_HASHED_PASSWORD,
                           disabled=False)

class FakeAuthManager(AuthManagerBaseClass):

    auth_cookie: str = None

    # Authentication

    def verify_password(self, plain_password, hashed_password):
        pass

    def get_password_hash(self, password):
        pass

    def get_entity(self, db, username: str):
        pass

    def authenticate_entity(self, fake_db, username: str, password: str):
        pass

    def create_access_token(self,
                            _: dict,
                            __: Union[timedelta, None] = None):
        return FAKE_ACCESS_TOKEN

    def access_token_is_valid(self, access_token: str) -> bool:
        return self.auth_cookie == access_token

    async def get_current_auth_entity(self, _: Annotated[str, Depends(OAUTH2_SCHEME)]):
        return FAKE_USER_IN_DB

    async def get_current_active_auth_entity(self,
                                             _: Annotated[User, Depends(get_current_auth_entity)]):
        FAKE_USER_IN_DB

    def update_auth_token_for_entity(self, user: User, response: Response):
        pass

    async def refresh_session(self,
                              user: User,
                              response: Response,
                              session_id: Annotated[Union[str, None], Cookie()] = None) -> SessionRefreshData | None:
        token = Token(access_token=FAKE_ACCESS_TOKEN, token_type="bearer")
        return SessionRefreshData(session_id=FAKE_SESSION_ID,
                                  auth_token=token)

    def datastore_user_instance(self, access_token, refresh_token) -> Client:
        return None

    def datastore_admin_instance(self) -> Client:
        return None

    def get_monitoring_proxy_url(self) -> str:
        return ""

    def is_monitoring_proxy_reachable(self) -> bool:
        return False

    def create_monitoring_proxy_config(self, cache_max_age, llm_model):
        return {}

    def create_monitoring_proxy_headers(self, **kwargs):
        return {}
