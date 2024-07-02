import json

from fastapi import (APIRouter,
                     Cookie,
                     Depends,
                     HTTPException,
                     Response,
                     status,)
from fastapi.security import OAuth2PasswordRequestForm
from langcodes import Language
from supabase import Client
from typing import Annotated, Union

from ..api.auth_base_class import AuthManagerBaseClass
from ..internal import logging, model, security
from ..internal.utilities import datetime_handler

class SecurityRouter:

    ROUTER_TAG = "security"
    LOGOUT_ENDPOINT = "/logout"
    SIGN_UP_ENDPOINT = "/sign-up"
    TOKEN_ENDPOINT = "/token"

    def __init__(self, auth_manager: AuthManagerBaseClass):
        self._auth_manager = auth_manager
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.TOKEN_ENDPOINT, tags=[self.ROUTER_TAG])
        async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                         response: Response,
                                         session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
            return await self._login_for_access_token_internal(form_data=form_data,
                                                               response=response,
                                                               session_id=session_id)

        @self.router.post(self.SIGN_UP_ENDPOINT, tags=[self.ROUTER_TAG])
        async def sign_up(signup_data: model.SignupData,
                          response: Response,
                          authorization: Annotated[Union[str, None], Cookie()] = None,
                          current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._sign_up_internal(signup_data=signup_data,
                                                response=response,
                                                authorization=authorization,
                                                current_session_id=current_session_id)

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def logout(response: Response,
                         therapist_id: str,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(response=response,
                                               therapist_id=therapist_id,
                                               authorization=authorization,
                                               current_session_id=current_session_id)

    """
    Returns an oauth token to be used for invoking the endpoints.

    Arguments:
    form_data  – the data required to validate the user.
    response – The response object to be used for creating the final response.
    session_id  – the id of the current user session.
    """
    async def _login_for_access_token_internal(self,
                                               form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                               response: Response,
                                               session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
        try:
            user = self._auth_manager.authenticate_entity(security.users_db, form_data.username, form_data.password)
            assert user

            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=user,
                                                                                                      response=response,
                                                                                                      session_id=session_id)
            new_session_id = session_refresh_data._session_id
            logging.log_api_response(session_id=new_session_id,
                                    endpoint_name=self.TOKEN_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST,
                                    description=f"Refreshing token from {session_id} to {new_session_id}")

            return session_refresh_data._auth_token
        except Exception as e:
            raise HTTPException(detail="Invalid credentials", status_code=status.HTTP_400_BAD_REQUEST)

    """
    Signs up a new user.

    Arguments:
    signup_data – the data to be used to sign up the user.
    response – the response model to be used for creating the final response.
    authorization – The authorization cookie, if exists.
    current_session_id – The session_id cookie, if exists.
    """
    async def _sign_up_internal(self,
                                signup_data: model.SignupData,
                                response: Response,
                                authorization: Annotated[Union[str, None], Cookie()] = None,
                                current_session_id: Annotated[Union[str, None], Cookie()] = None):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_POST,
                                endpoint_name=self.SIGN_UP_ENDPOINT,
                                auth_entity=current_entity.username)

        try:
            assert datetime_handler.is_valid_date(signup_data.birth_date), "Invalid date. The expected format is mm-dd-yyyy"
            assert Language.get(signup_data.language_preference).is_valid(), "Invalid language_preference parameter"

            datastore_client: Client = self._auth_manager.datastore_admin_instance()
            res = datastore_client.auth.sign_up({
                "email": signup_data.user_email,
                "password": signup_data.user_password,
            })

            json_response = json.loads(res.json())
            user_role = json_response["user"]["role"]
            access_token = json_response["session"]["access_token"]
            refresh_token = json_response["session"]["refresh_token"]
            assert (user_role == 'authenticated'
                and access_token
                and refresh_token), "Something went wrong when signing up the user"

            user_id = json_response["user"]["id"]
            datastore_client.table('therapists').insert({
                "id": user_id,
                "first_name": signup_data.first_name,
                "middle_name": signup_data.middle_name,
                "last_name": signup_data.last_name,
                "birth_date": signup_data.birth_date,
                "login_mechanism": signup_data.signup_mechanism,
                "email": signup_data.user_email,
                "language_preference": signup_data.language_preference,
            }).execute()

            logging.log_api_response(therapist_id=user_id,
                                    session_id=session_id,
                                    endpoint_name=self.SIGN_UP_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST)

            return {
                "user_id": user_id,
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_417_EXPECTATION_FAILED
            logging.log_error(session_id=session_id,
                            endpoint_name=self.SIGN_UP_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Logs out the user.

    Arguments:
    response – the object to be used for constructing the final response.
    therapist_id – The therapist id associated with the operation.
    authorization – The authorization cookie, if exists.
    current_session_id – The session_id cookie, if exists.
    """
    async def _logout_internal(self,
                               response: Response,
                               therapist_id: str,
                               authorization: Annotated[Union[str, None], Cookie()] = None,
                               current_session_id: Annotated[Union[str, None], Cookie()] = None):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=therapist_id,
                                method=logging.API_METHOD_POST,
                                endpoint_name=self.LOGOUT_ENDPOINT,
                                auth_entity=current_entity.username)

        self._auth_manager.logout(response)

        logging.log_api_response(session_id=session_id,
                                therapist_id=therapist_id,
                                endpoint_name=self.LOGOUT_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_POST)

        return {}
