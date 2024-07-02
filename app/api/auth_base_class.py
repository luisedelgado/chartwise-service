from abc import ABC
from datetime import timedelta

from fastapi import Cookie, Depends, Response
from supabase import Client
from typing import Annotated, Union

from ..internal.model import SessionRefreshData
from ..internal.security import OAUTH2_SCHEME, User

class AuthManagerBaseClass(ABC):

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

    """
    Refreshes the user's auth token for a continued session experience.

    Arguments:
    user – The user for whom to refresh the session.
    response  – the model with which to build the API response.
    """
    def update_auth_token_for_entity(self, user: User, response: Response):
        pass

    """
    Validates the incoming session cookies.

    Arguments:
    user – the user for whom to refresh the current session.
    response – the response object where we can update cookies.
    current_session_id – the session_id cookie to be validated, if exists.
    """
    async def refresh_session(self,
                              user: User,
                              response: Response,
                              session_id: Annotated[Union[str, None], Cookie()] = None) -> SessionRefreshData | None:
        pass

    """
    Returns an active supabase instance based on a user's auth tokens.

    Arguments:
    access_token – the access_token associated with a live supabase session.
    refresh_token – the refresh_token associated with a live supabase session.
    """
    def datastore_user_instance(access_token, refresh_token) -> Client:
        pass

    """
    Returns an active supabase instance with admin priviledges.
    """
    def datastore_admin_instance() -> Client:
        pass

    """
    Returns whether or not the monitoring proxy is reachable.
    """
    def is_monitoring_proxy_reachable() -> bool:
        pass

    """
    Returns the monitoring proxy url.
    """
    def get_monitoring_proxy_url() -> str:
        pass

    """
    Returns a config to be used for the monitoring proxy.

    Arguments:
    cache_max_age – the ttl of the cache.
    llm_model – the llm_model used.
    """
    def create_monitoring_proxy_config(cache_max_age, llm_model):
        pass

    """
    Returns a set of headers to be used for the monitoring proxy service.

    Arguments:
    kwargs  – the set of optional arguments.
    """
    def create_monitoring_proxy_headers(**kwargs):
        pass

    """
    Logs out a user.

    response – the response object to be used for modeling the client response.
    """
    def logout(response: Response):
        pass
