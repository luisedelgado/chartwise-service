from abc import ABC
from datetime import timedelta

from fastapi import Cookie, Depends, Request, Response
from supabase import Client
from typing import Annotated, Union

from ..internal.model import SessionRefreshData
from ..internal.security import OAUTH2_SCHEME, User

class AuthManagerBaseClass(ABC):

    # Authentication

    """
    Returns a flag determining if the password matches the hashed password.

    Arguments:
    password – the password to be verified.
    hashed_password – the hashed password to be used as a benchmark.
    """
    def verify_password(self, plain_password, hashed_password):
        pass

    """
    Returns the password hash from the incoming password.

    Arguments:
    password – the password to be hashed.
    """
    def get_password_hash(self, password):
        pass

    """
    Returns the full entity from the incoming username.

    Arguments:
    db – the db where the entity will be queried for.
    username – the username to be used for querying.
    """
    def get_entity(self, db, username: str):
        pass

    """
    Authenticates an entity.

    Arguments:
    db – the db against which authentication will be attempted.
    username – the username to be used for authentication.
    password – the password to be used for authentication.
    """
    def authenticate_entity(self, db, username: str, password: str):
        pass

    """
    Authenticates a datastore user.

    Arguments:
    user_id – the id associated with the user that's being authenticated.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    """
    def authenticate_datastore_user(self,
                                    user_id: str,
                                    datastore_access_token: str,
                                    datastore_refresh_token: str) -> bool:
        pass

    """
    Creates an access token to be used in the session.

    Arguments:
    data – the data to be used for encoding into the token.
    expires_delta – the expiration timestamp on the token.
    """
    def create_access_token(self,
                            data: dict,
                            expires_delta: Union[timedelta, None] = None):
        pass

    """
    Returns a flag determining if the incoming access token is still valid.

    Arguments:
    access_token – the token to be validated.
    """
    def access_token_is_valid(self, access_token: str) -> bool:
        pass

    """
    Returns the current auth entity.

    Arguments:
    token – the current alive token that's being used in the session.
    """
    async def get_current_auth_entity(self, token: Annotated[str, Depends(OAUTH2_SCHEME)]):
        pass

    """
    Returns the currently active auth entity.

    Arguments:
    user – the user for whom to refresh the session.
    current_auth_entity – the current auth entity (to be determined if active or not).
    """
    async def get_current_active_auth_entity(self,
                                             current_auth_entity: Annotated[User, Depends(get_current_auth_entity)]):
        pass

    """
    Refreshes the user's auth token for a continued session experience.

    Arguments:
    user_id – the user id for whom to refresh the session.
    response – the model with which to build the API response.
    """
    def update_auth_token_for_entity(self, user_id: str, response: Response):
        pass

    """
    Validates the incoming session cookies.

    Arguments:
    user_id – the user for whom to refresh the current session.
    request – the incoming request object.
    response – the response object where we can update cookies.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    current_session_id – the session_id cookie to be validated, if exists.
    """
    async def refresh_session(self,
                              user_id: str,
                              request: Request,
                              response: Response,
                              datastore_access_token: str = None,
                              datastore_refresh_token: str = None,
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
    kwargs – the set of optional arguments.
    """
    def create_monitoring_proxy_headers(**kwargs):
        pass

    """
    Logs out a user.

    response – the response object to be used for modeling the client response.
    """
    def logout(response: Response):
        pass
