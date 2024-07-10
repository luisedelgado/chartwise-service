import json

from fastapi import (APIRouter,
                     Cookie,
                     Depends,
                     HTTPException,
                     Request,
                     Response,
                     status,)
from langcodes import Language, tag_parser
from supabase import Client
from typing import Annotated, Union

from ..api.auth_base_class import AuthManagerBaseClass
from ..api.assistant_base_class import AssistantManagerBaseClass
from ..internal import logging, model, security
from ..internal.utilities import datetime_handler

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
        async def login_for_access_token(body: model.LoginData,
                                         response: Response,
                                         request: Request,
                                         session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
            return await self._login_for_access_token_internal(body=body,
                                                               request=request,
                                                               response=response,
                                                               session_id=session_id)

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def logout(response: Response,
                         request: Request,
                         logout_data: model.LogoutData,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(response=response,
                                               request=request,
                                               therapist_id=logout_data.therapist_id,
                                               authorization=authorization,
                                               current_session_id=current_session_id)

        @self.router.post(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def add_new_therapist(body: model.TherapistInsertPayload,
                                    response: Response,
                                    request: Request,
                                    datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                    datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                    authorization: Annotated[Union[str, None], Cookie()] = None,
                                    current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_new_therapist_internal(body=body,
                                                          response=response,
                                                          request=request,
                                                          datastore_access_token=datastore_access_token,
                                                          datastore_refresh_token=datastore_refresh_token,
                                                          authorization=authorization,
                                                          current_session_id=current_session_id)

        @self.router.put(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_therapist_data(response: Response,
                                        request: Request,
                                        body: model.TherapistUpdatePayload,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_therapist_data_internal(response=response,
                                                              request=request,
                                                              body=body,
                                                              datastore_access_token=datastore_access_token,
                                                              datastore_refresh_token=datastore_refresh_token,
                                                              authorization=authorization,
                                                              current_session_id=current_session_id)

        @self.router.delete(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_all_therapist_data(response: Response,
                                            request: Request,
                                            id: str = None,
                                            datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                            datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                            authorization: Annotated[Union[str, None], Cookie()] = None,
                                            current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_all_therapist_data_internal(response=response,
                                                                  request=request,
                                                                  id=id,
                                                                  datastore_access_token=datastore_access_token,
                                                                  datastore_refresh_token=datastore_refresh_token,
                                                                  authorization=authorization,
                                                                  current_session_id=current_session_id)

    """
    Returns an oauth token to be used for invoking the endpoints.

    Arguments:
    body – the body associated with the request.
    request – the incoming request object.
    response – the response object to be used for creating the final response.
    session_id – the id of the current user session.
    """
    async def _login_for_access_token_internal(self,
                                               body: model.LoginData,
                                               request: Request,
                                               response: Response,
                                               session_id: Annotated[Union[str, None], Cookie()]) -> security.Token:
        try:
            authenticated_successfully = self._auth_manager.authenticate_datastore_user(user_id=body.user_id,
                                                                                        datastore_access_token=body.datastore_access_token,
                                                                                        datastore_refresh_token=body.datastore_refresh_token)
            assert authenticated_successfully, "Failed to authenticate the user. Check the tokens you are sending."

            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user_id=body.user_id,
                                                                                                      request=request,
                                                                                                      response=response,
                                                                                                      session_id=session_id,
                                                                                                      datastore_access_token=body.datastore_access_token,
                                                                                                      datastore_refresh_token=body.datastore_refresh_token)
            new_session_id = session_refresh_data._session_id

            logging.log_api_response(session_id=new_session_id,
                                     endpoint_name=self.TOKEN_ENDPOINT,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_POST,
                                     description=f"Refreshing token from {session_id} to {new_session_id}")

            return session_refresh_data._auth_token
        except Exception as e:
            raise HTTPException(detail=str(e), status_code=status.HTTP_400_BAD_REQUEST)

    """
    Logs out the user.

    Arguments:
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    therapist_id – the therapist id associated with the operation.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _logout_internal(self,
                               response: Response,
                               request: Request,
                               therapist_id: str,
                               authorization: Annotated[Union[str, None], Cookie()],
                               current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        try:
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user_id=therapist_id,
                                                                                                      request=request,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=therapist_id,
                                method=logging.API_METHOD_POST,
                                endpoint_name=self.LOGOUT_ENDPOINT,)

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
    body – the body associated with the request.
    request – the incoming request object.
    response – the response model to be used for creating the final response.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _add_new_therapist_internal(self,
                                          body: model.TherapistInsertPayload,
                                          request: Request,
                                          response: Response,
                                          datastore_access_token: Annotated[Union[str, None], Cookie()],
                                          datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                          authorization: Annotated[Union[str, None], Cookie()],
                                          current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user_id=body.id,
                                                                                                      request=request,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_POST,
                                endpoint_name=self.THERAPISTS_ENDPOINT)

        try:
            assert body.signup_mechanism != model.SignupMechanism.UNDEFINED, '''Invalid parameter 'undefined' for signup_mechanism.'''
            assert body.gender != model.Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date format. The expected format is mm-dd-yyyy"
            assert Language.get(body.language_code_preference).is_valid(), "Invalid language_preference parameter"

            datastore_client: Client = self._auth_manager.datastore_user_instance(refresh_token=datastore_refresh_token,
                                                                                  access_token=datastore_access_token)
            datastore_client.table('therapists').insert({
                "id": body.id,
                "first_name": body.first_name,
                "middle_name": body.middle_name,
                "last_name": body.last_name,
                "gender": body.gender.value,
                "birth_date": body.birth_date,
                "login_mechanism": body.signup_mechanism.value,
                "email": body.email,
                "language_preference": body.language_code_preference,
            }).execute()

            logging.log_api_response(therapist_id=body.id,
                                    session_id=session_id,
                                    endpoint_name=self.THERAPISTS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST)

            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if (type(e) == AssertionError or type(e) == tag_parser.LanguageTagError) else status.HTTP_417_EXPECTATION_FAILED
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
    request – the incoming request object.
    body – the body associated with the request.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _update_therapist_data_internal(self,
                                              response: Response,
                                              request: Request,
                                              body: model.TherapistUpdatePayload,
                                              datastore_access_token: Annotated[Union[str, None], Cookie()],
                                              datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                              authorization: Annotated[Union[str, None], Cookie()],
                                              current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user_id=body.id,
                                                                                                      request=request,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=body.id,
                                method=logging.API_METHOD_PUT,
                                endpoint_name=self.THERAPISTS_ENDPOINT)
        try:
            assert body.gender != model.Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date format. The expected format is mm-dd-yyyy"
            assert Language.get(body.language_code_preference).is_valid(), "Invalid language_preference parameter"

            datastore_client: Client = self._auth_manager.datastore_user_instance(refresh_token=datastore_refresh_token,
                                                                                  access_token=datastore_access_token)
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
            status_code = status.HTTP_400_BAD_REQUEST if (type(e) == AssertionError or type(e) == tag_parser.LanguageTagError) else status.HTTP_417_EXPECTATION_FAILED
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
    request – the incoming request object.
    id – the id associated with the therapist data to be deleted.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _delete_all_therapist_data_internal(self,
                                                  response: Response,
                                                  request: Request,
                                                  id: str,
                                                  datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                  datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                  authorization: Annotated[Union[str, None], Cookie()],
                                                  current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        if len(id or '') == 0:
            raise HTTPException(detail="Invalid or empty id to be deleted", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user_id=id,
                                                                                                      response=response,
                                                                                                      request=request,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=id,
                                method=logging.API_METHOD_DELETE,
                                endpoint_name=self.THERAPISTS_ENDPOINT)
        try:
            datastore_client: Client = self._auth_manager.datastore_user_instance(refresh_token=datastore_refresh_token,
                                                                                  access_token=datastore_access_token)

            # Delete therapist and all their patients (through cascading)
            datastore_client.table('therapists').delete().eq('id', id).execute()

            # Remove the active session and clear Auth data from client storage.
            datastore_client.auth.sign_out()

            # Delete vectors associated with therapist's patients
            self._assistant_manager.delete_all_sessions_for_therapist(id)

            # Delete auth and session cookies
            self._auth_manager.logout(response)

            logging.log_account_deletion(therapist_id=id)
            logging.log_api_response(therapist_id=id,
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
