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
from ..api.assistant_base_class import AssistantManagerBaseClass
from ..internal import logging, model, security
from ..internal.utilities import datetime_handler, general_utilities

class SecurityRouter:

    ROUTER_TAG = "authentication"
    LOGOUT_ENDPOINT = "/v1/logout"
    TOKEN_ENDPOINT = "/token"
    THERAPISTS_ENDPOINT = "/v1/therapists"

    def __init__(self,
                 auth_manager: AuthManagerBaseClass,
                 assistant_manager: AssistantManagerBaseClass):
        self._auth_manager = auth_manager
        self._assistant_manager = assistant_manager
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

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def logout(response: Response,
                         logout_data: model.LogoutData,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(response=response,
                                               therapist_id=logout_data.therapist_id,
                                               authorization=authorization,
                                               current_session_id=current_session_id)

        @self.router.post(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def signup_new_therapist(signup_data: model.SignupData,
                                       response: Response,
                                       authorization: Annotated[Union[str, None], Cookie()] = None,
                                       current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._signup_new_therapist_internal(signup_data=signup_data,
                                                             response=response,
                                                             authorization=authorization,
                                                             current_session_id=current_session_id)

        @self.router.put(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_therapist_data(response: Response,
                                        body: model.TherapistUpdatePayload,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_therapist_data_internal(response=response,
                                                              body=body,
                                                              authorization=authorization,
                                                              current_session_id=current_session_id)

        @self.router.delete(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_all_therapist_data(response: Response,
                                            body: model.TherapistDeletePayload,
                                            authorization: Annotated[Union[str, None], Cookie()] = None,
                                            current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_all_therapist_data_internal(response=response,
                                                                  body=body,
                                                                  authorization=authorization,
                                                                  current_session_id=current_session_id)

    """
    Returns an oauth token to be used for invoking the endpoints.

    Arguments:
    form_data – the data required to validate the user.
    response – the response object to be used for creating the final response.
    session_id – the id of the current user session.
    """
    async def _login_for_access_token_internal(self,
                                               form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                               response: Response,
                                               session_id: Annotated[Union[str, None], Cookie()]) -> security.Token:
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
    Logs out the user.

    Arguments:
    response – the object to be used for constructing the final response.
    therapist_id – the therapist id associated with the operation.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _logout_internal(self,
                               response: Response,
                               therapist_id: str,
                               authorization: Annotated[Union[str, None], Cookie()],
                               current_session_id: Annotated[Union[str, None], Cookie()]):
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

    """
    Signs up a new therapist user.

    Arguments:
    signup_data – the data to be used to sign up the user.
    response – the response model to be used for creating the final response.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _signup_new_therapist_internal(self,
                                             signup_data: model.SignupData,
                                             response: Response,
                                             authorization: Annotated[Union[str, None], Cookie()],
                                             current_session_id: Annotated[Union[str, None], Cookie()]):
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
                                endpoint_name=self.THERAPISTS_ENDPOINT,
                                auth_entity=current_entity.username)

        try:
            assert signup_data.signup_mechanism != model.SignupMechanism.UNDEFINED, '''Invalid parameter 'undefined' for signup_mechanism.'''
            assert signup_data.gender.value != model.Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(signup_data.birth_date), "Invalid date format. The expected format is mm-dd-yyyy"
            assert Language.get(signup_data.language_code_preference).is_valid(), "Invalid language_preference parameter"

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
                "gender": signup_data.gender.value,
                "birth_date": signup_data.birth_date,
                "login_mechanism": signup_data.signup_mechanism.value,
                "email": signup_data.user_email,
                "language_preference": signup_data.language_code_preference,
            }).execute()

            logging.log_api_response(therapist_id=user_id,
                                    session_id=session_id,
                                    endpoint_name=self.THERAPISTS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST)

            return {
                "id": user_id,
                "datastore_access_token": access_token,
                "datastore_refresh_token": refresh_token
            }
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_417_EXPECTATION_FAILED
            logging.log_error(session_id=session_id,
                              endpoint_name=self.THERAPISTS_ENDPOINT,
                              error_code=status_code,
                              description=description,
                              method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates data associated with a therapist.

    Arguments:
    response – the object to be used for constructing the final response.
    body – the body associated with the request.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _update_therapist_data_internal(self,
                                              response: Response,
                                              body: model.TherapistUpdatePayload,
                                              authorization: Annotated[Union[str, None], Cookie()],
                                              current_session_id: Annotated[Union[str, None], Cookie()]):
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
                                therapist_id=body.id,
                                method=logging.API_METHOD_PUT,
                                endpoint_name=self.THERAPISTS_ENDPOINT,
                                auth_entity=current_entity.username)
        try:
            assert body.gender != model.Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date format. The expected format is mm-dd-yyyy"
            assert Language.get(body.language_code_preference).is_valid(), "Invalid language_preference parameter"

            datastore_client: Client = self._auth_manager.datastore_user_instance(refresh_token=body.datastore_refresh_token,
                                                                                  access_token=body.datastore_access_token)
            datastore_client.table('therapists').update({
                "first_name": body.first_name,
                "middle_name": body.middle_name,
                "last_name": body.last_name,
                "gender": body.gender.value,
                "birth_date": body.birth_date,
                "email": body.email,
                "language_preference": body.language_code_preference,
            }).eq('id', body.id).execute()

            logging.log_api_response(therapist_id=body.id,
                                     session_id=session_id,
                                     endpoint_name=self.THERAPISTS_ENDPOINT,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_PUT)
            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST
            logging.log_error(session_id=session_id,
                              endpoint_name=self.THERAPISTS_ENDPOINT,
                              error_code=status_code,
                              description=description,
                              method=logging.API_METHOD_PUT)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes all data associated with a therapist.

    Arguments:
    response – the object to be used for constructing the final response.
    body – the body associated with the request.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _delete_all_therapist_data_internal(self,
                                                  response: Response,
                                                  body: model.TherapistDeletePayload,
                                                  authorization: Annotated[Union[str, None], Cookie()],
                                                  current_session_id: Annotated[Union[str, None], Cookie()]):
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
                                therapist_id=body.id,
                                method=logging.API_METHOD_DELETE,
                                endpoint_name=self.THERAPISTS_ENDPOINT,
                                auth_entity=current_entity.username)
        try:
            datastore_client: Client = self._auth_manager.datastore_user_instance(refresh_token=body.datastore_refresh_token,
                                                                                  access_token=body.datastore_access_token)

            # Delete therapist and all their patients (through cascading)
            datastore_client.table('therapists').delete().eq('id', body.id).execute()

            # Remove the active session and clear Auth data from client storage.
            datastore_client.auth.sign_out()

            # Delete vectors associated with therapist's patients
            self._assistant_manager.delete_all_sessions_for_therapist(body)

            # Delete auth and session cookies
            self._auth_manager.logout(response)

            logging.log_account_deletion(therapist_id=body.id)
            logging.log_api_response(therapist_id=body.id,
                                     session_id=session_id,
                                     endpoint_name=self.THERAPISTS_ENDPOINT,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_DELETE)
            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST
            logging.log_error(session_id=session_id,
                              endpoint_name=self.THERAPISTS_ENDPOINT,
                              error_code=status_code,
                              description=description,
                              method=logging.API_METHOD_DELETE)
            raise HTTPException(status_code=status_code,
                                detail=description)
