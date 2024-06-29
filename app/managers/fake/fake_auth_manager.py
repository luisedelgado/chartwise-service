from datetime import timedelta

from fastapi import Cookie, Depends, Response
from supabase import Client
from typing import Annotated, Union

from ...internal.model import SessionRefreshData
from ...internal.security import OAUTH2_SCHEME, User
from ...api.auth_base_class import AuthManagerBaseClass

class FakeAuthManager(AuthManagerBaseClass):
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
                            data: dict,
                            expires_delta: Union[timedelta, None] = None):
        pass

    def access_token_is_valid(self, access_token: str) -> bool:
        pass

    async def get_current_auth_entity(self, token: Annotated[str, Depends(OAUTH2_SCHEME)]):
        pass

    async def get_current_active_auth_entity(self,
                                             current_auth_entity: Annotated[User, Depends(get_current_auth_entity)]):
        pass

    def update_auth_token_for_entity(self, user: User, response: Response):
        pass

    async def refresh_session(self,
                              user: User,
                              response: Response,
                              session_id: Annotated[Union[str, None], Cookie()] = None) -> SessionRefreshData | None:
        pass

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
