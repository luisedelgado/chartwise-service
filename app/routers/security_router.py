import uuid

from enum import Enum
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import (APIRouter,
                     BackgroundTasks,
                     Body,
                     Cookie,
                     Depends,
                     Header,
                     HTTPException,
                     Response,
                     status,)
from langcodes import Language
from typing import Annotated, Optional, Union
from pydantic import BaseModel

from ..internal import security
from ..internal.dependency_container import dependency_container
from ..internal.logging import (API_METHOD_DELETE,
                                API_METHOD_POST,
                                API_METHOD_PUT,
                                log_account_deletion,
                                log_api_request,
                                log_api_response,
                                log_error)
from ..internal.schemas import Gender
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager

class LoginMechanism(Enum):
    UNDEFINED = "undefined"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    INTERNAL = "internal"

class SignupPayload(BaseModel):
    email: str
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    login_mechanism: LoginMechanism
    language_preference: str
    gender: Optional[Gender] = None

class TherapistUpdatePayload(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[str] = None
    language_preference: Optional[str] = None
    gender: Optional[Gender] = None

class SecurityRouter:

    ROUTER_TAG = "authentication"
    LOGOUT_ENDPOINT = "/v1/logout"
    ACCOUNT_ENDPOINT = "/v1/account"
    SIGNIN_ENDPOINT = "/v1/signin"
    SESSION_REFRESH_ENDPOINT = "/v1/session-refresh"
    SIGNUP_ENDPOINT = "/v1/signup"

    def __init__(self):
        self._auth_manager = AuthManager()
        self._assistant_manager = AssistantManager()
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.SIGNIN_ENDPOINT, tags=[self.ROUTER_TAG])
        async def signin(credentials_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                         background_tasks: BackgroundTasks,
                         response: Response,
                         session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
            return await self._signin_internal(credentials_data=credentials_data,
                                               background_tasks=background_tasks,
                                               response=response,
                                               session_id=session_id)

        @self.router.put(self.SESSION_REFRESH_ENDPOINT, tags=[self.ROUTER_TAG])
        async def refresh_auth_token(response: Response,
                                     store_access_token: Annotated[str | None, Header()] = None,
                                     store_refresh_token: Annotated[str | None, Header()] = None,
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
            return await self._refresh_auth_token_internal(authorization=authorization,
                                                           response=response,
                                                           store_access_token=store_access_token,
                                                           store_refresh_token=store_refresh_token,
                                                           session_id=session_id)

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def logout(response: Response,
                         background_tasks: BackgroundTasks,
                         store_access_token: Annotated[str | None, Header()] = None,
                         store_refresh_token: Annotated[str | None, Header()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(response=response,
                                               store_access_token=store_access_token,
                                               store_refresh_token=store_refresh_token,
                                               background_tasks=background_tasks,
                                               session_id=session_id)

        @self.router.post(self.SIGNUP_ENDPOINT, tags=[self.ROUTER_TAG])
        async def signup(body: SignupPayload,
                         response: Response,
                         password: Annotated[str, Body()] = None,
                         store_access_token: Annotated[str | None, Header()] = None,
                         store_refresh_token: Annotated[str | None, Header()] = None,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._signup_internal(body=body,
                                               password=password,
                                               response=response,
                                               store_access_token=store_access_token,
                                               store_refresh_token=store_refresh_token,
                                               authorization=authorization,
                                               session_id=session_id)

        @self.router.put(self.ACCOUNT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_account_data(response: Response,
                                      background_tasks: BackgroundTasks,
                                      body: TherapistUpdatePayload,
                                      store_access_token: Annotated[str | None, Header()] = None,
                                      store_refresh_token: Annotated[str | None, Header()] = None,
                                      authorization: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_account_data_internal(response=response,
                                                            background_tasks=background_tasks,
                                                            body=body,
                                                            store_access_token=store_access_token,
                                                            store_refresh_token=store_refresh_token,
                                                            authorization=authorization,
                                                            session_id=session_id)

        @self.router.delete(self.ACCOUNT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_all_account_data(response: Response,
                                          background_tasks: BackgroundTasks,
                                          store_access_token: Annotated[str | None, Header()] = None,
                                          store_refresh_token: Annotated[str | None, Header()] = None,
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_all_account_data_internal(response=response,
                                                                background_tasks=background_tasks,
                                                                store_access_token=store_access_token,
                                                                store_refresh_token=store_refresh_token,
                                                                authorization=authorization,
                                                                session_id=session_id)

    """
    Returns an oauth token to be used for invoking the endpoints.

    Arguments:
    credentials_data – the credentials data to be used for authentication.
    background_tasks – object for scheduling concurrent tasks.
    response – the response object to be used for creating the final response.
    session_id – the id of the current user session.
    """
    async def _signin_internal(self,
                               credentials_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                               background_tasks: BackgroundTasks,
                               response: Response,
                               session_id: Annotated[Union[str, None], Cookie()]) -> security.Token:
        try:
            if session_id is None:
                session_id = uuid.uuid1()
                response.set_cookie(key="session_id",
                                    value=session_id,
                                    domain=self._auth_manager.APP_COOKIE_DOMAIN,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")

            post_api_method = API_METHOD_POST
            log_api_request(background_tasks=background_tasks,
                            session_id=session_id,
                            method=post_api_method,
                            endpoint_name=self.SIGNIN_ENDPOINT)

            user_id = self._auth_manager.authenticate_store_user(username=credentials_data.username,
                                                                 password=credentials_data.password)
            assert len(user_id or '') > 0, "Failed to authenticate the user. Check the tokens you are sending."

            auth_token = await self._auth_manager.refresh_session(user_id=user_id,
                                                                  response=response)
            await dependency_container.inject_openai_client().clear_chat_history()
            log_api_response(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.SIGNIN_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             therapist_id=user_id,
                             method=post_api_method)
            return auth_token
        except Exception as e:
            status_code = status.HTTP_401_UNAUTHORIZED
            description = str(e)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SIGNIN_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=post_api_method)
            raise HTTPException(detail=description, status_code=status_code)

    """
    Refreshes an oauth token to be used for invoking the endpoints.

    Arguments:
    authorization – the authorization cookie, if exists.
    background_tasks – object for scheduling concurrent tasks.
    response – the response object to be used for creating the final response.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the id of the current user session.
    """
    async def _refresh_auth_token_internal(self,
                                           authorization: Annotated[Union[str, None], Cookie()],
                                           background_tasks: BackgroundTasks,
                                           response: Response,
                                           store_access_token: Annotated[str | None, Header()],
                                           store_refresh_token: Annotated[str | None, Header()],
                                           session_id: Annotated[Union[str, None], Cookie()]) -> security.Token:
        put_api_method = API_METHOD_PUT
        try:
            if not self._auth_manager.access_token_is_valid(authorization):
                raise security.AUTH_TOKEN_EXPIRED_ERROR

            log_api_request(background_tasks=background_tasks,
                            session_id=session_id,
                            method=put_api_method,
                            endpoint_name=self.SESSION_REFRESH_ENDPOINT)

            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)

            user_id = supabase_client.get_current_user_id()
            token = await self._auth_manager.refresh_session(user_id=user_id, response=response)

            log_api_response(background_tasks=background_tasks,
                             session_id=session_id,
                             therapist_id=user_id,
                             method=put_api_method,
                             endpoint_name=self.SESSION_REFRESH_ENDPOINT)
            return token
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SESSION_REFRESH_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=put_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Logs out the user.

    Arguments:
    response – the object to be used for constructing the final response.
    background_tasks – object for scheduling concurrent tasks.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _logout_internal(self,
                               response: Response,
                               background_tasks: BackgroundTasks,
                               store_access_token: Annotated[str | None, Header()],
                               store_refresh_token: Annotated[str | None, Header()],
                               session_id: Annotated[Union[str, None], Cookie()]):
        user_id = None
        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(refresh_token=store_access_token,
                                                                                                         access_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
        except Exception:
            pass

        self._auth_manager.logout(response)
        background_tasks.add_task(dependency_container.inject_openai_client().clear_chat_history)

        if user_id is not None:
            background_tasks.add_task(self._schedule_logout_activity_logging,
                                      background_tasks,
                                      user_id,
                                      session_id)
        return {}

    """
    Signs up a new therapist user.

    Arguments:
    body – the body associated with the request.
    password – the password associated with the new account.
    background_tasks – object for scheduling concurrent tasks.
    response – the response model to be used for creating the final response.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _signup_internal(self,
                               body: SignupPayload,
                               password: str,
                               background_tasks: BackgroundTasks,
                               response: Response,
                               store_access_token: Annotated[str | None, Header()],
                               store_refresh_token: Annotated[str | None, Header()],
                               authorization: Annotated[Union[str, None], Cookie()],
                               session_id: Annotated[Union[str, None], Cookie()]):
        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        post_api_method = API_METHOD_POST

        try:
            # This endpoint is allowed to be invoked in a user's zero journey when creating an account.
            # The flow is to first add the user to the auth table, and then this codepath adds them to the therapists' table.
            # Because of this, the client may not have an auth cookie yet, so if it isn't present, we'll attempt authentication.
            credentials_data = OAuth2PasswordRequestForm(username=body.email, password=password)
            authorization_data = await self._signin_internal(credentials_data=credentials_data,
                                                             response=response,
                                                             session_id=session_id)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SIGNUP_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=post_api_method)
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        logs_request_description = "".join([
            "birthdate=\"",
            f"{body.birth_date or ''}\";",
            "login_mechanism=\"",
            f"{body.login_mechanism or ''}\";",
            "language_preference=\"",
            f"{body.language_preference or ''}\";",
            "gender=\"",
            f"{body.gender or ''}\""
        ])

        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        description=logs_request_description,
                        method=post_api_method,
                        endpoint_name=self.SIGNUP_ENDPOINT)

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SIGNUP_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=post_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.dict(exclude_unset=True)

            assert body['login_mechanism'] != LoginMechanism.UNDEFINED, '''Invalid parameter 'undefined' for login_mechanism.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            payload = {
                'id': user_id
            }
            for key, value in body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            supabase_client.insert(payload=payload, table_name="therapists")

            log_api_response(background_tasks=background_tasks,
                             therapist_id=user_id,
                             session_id=session_id,
                             endpoint_name=self.SIGNUP_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=post_api_method)

            response_payload = {
                "therapist_id": user_id
            }
            response_payload.update(authorization_data)
            return response_payload
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SIGNUP_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=post_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates data associated with a therapist.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    response – the object to be used for constructing the final response.
    body – the body associated with the request.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_account_data_internal(self,
                                            background_tasks: BackgroundTasks,
                                            response: Response,
                                            body: TherapistUpdatePayload,
                                            store_access_token: Annotated[str | None, Header()],
                                            store_refresh_token: Annotated[str | None, Header()],
                                            authorization: Annotated[Union[str, None], Cookie()],
                                            session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        put_api_method = API_METHOD_PUT
        description = "".join([
            "birthdate=\"",
            f"{body.birth_date or ''}\";",
            "language_preference=\"",
            f"{body.language_preference or ''}\";",
            "gender=\"",
            f"{body.gender or ''}\""
        ])
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=put_api_method,
                        description=description,
                        endpoint_name=self.ACCOUNT_ENDPOINT)

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.ACCOUNT_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=put_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.dict(exclude_unset=True)
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert 'language_preference' not in body or Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            payload = {}
            for key, value in body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            update_response = supabase_client.update(table_name="therapists",
                                                     payload=payload,
                                                     filters={
                                                         'id': user_id
                                                     })
            assert (0 != len((update_response).data)), "Update operation could not be completed."

            log_api_response(background_tasks=background_tasks,
                             therapist_id=user_id,
                             session_id=session_id,
                             endpoint_name=self.ACCOUNT_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=put_api_method)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.ACCOUNT_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=put_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes all data associated with a therapist.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    response – the object to be used for constructing the final response.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_all_account_data_internal(self,
                                                background_tasks: BackgroundTasks,
                                                response: Response,
                                                store_access_token: Annotated[str | None, Header()],
                                                store_refresh_token: Annotated[str | None, Header()],
                                                authorization: Annotated[Union[str, None], Cookie()],
                                                session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        delete_api_method = API_METHOD_DELETE
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=delete_api_method,
                        endpoint_name=self.ACCOUNT_ENDPOINT)

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.ACCOUNT_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=delete_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            patients_response = supabase_client.select(fields="id",
                                                       filters={
                                                           "therapist_id": user_id
                                                       },
                                                       table_name="patients")
            patients_response_data = patients_response.dict()
            assert 'data' in patients_response_data, "Failed to retrieve therapist data for patients"
            patient_ids = patients_response_data['data']

            # Delete therapist and all their patients (through cascading)
            delete_response = supabase_client.delete(table_name="therapists",
                                                     filters={
                                                         'id': user_id
                                                     })
            assert len(delete_response.dict()['data']) > 0, "No therapist found with the incoming id"

            # Remove the active session and clear Auth data from client storage.
            supabase_client.sign_out()

            # Delete vectors associated with therapist's patients
            self._assistant_manager.delete_all_sessions_for_therapist(user_id=user_id,
                                                                      patient_ids=patient_ids)

            # Delete auth and session cookies
            self._auth_manager.logout(response)

            log_account_deletion(background_tasks=background_tasks, therapist_id=user_id)
            log_api_response(background_tasks=background_tasks,
                             description=f"user_id: {user_id}",
                             session_id=session_id,
                             endpoint_name=self.ACCOUNT_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=delete_api_method)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.ACCOUNT_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=delete_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    async def _schedule_logout_activity_logging(self,
                                                background_tasks: BackgroundTasks,
                                                user_id: str,
                                                session_id: Annotated[Union[str, None], Cookie()]):
        try:
            post_api_method = API_METHOD_POST
            log_api_request(background_tasks=background_tasks,
                            session_id=session_id,
                            therapist_id=user_id,
                            method=post_api_method,
                            endpoint_name=self.LOGOUT_ENDPOINT)
            log_api_response(background_tasks=background_tasks,
                             session_id=session_id,
                             therapist_id=user_id,
                             endpoint_name=self.LOGOUT_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=post_api_method)
        except Exception:
            #Fail silently since there's no need to throw
            pass
