import uuid

from fastapi import (APIRouter,
                     Cookie,
                     HTTPException,
                     Request,
                     Response,
                     status,)
from supabase import Client
from typing import Annotated, Union

from ..api.assistant_base_class import AssistantManagerBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal import logging, model, security
from ..internal.utilities import datetime_handler, general_utilities

class AssistantRouter:

    SESSIONS_ENDPOINT = "/v1/sessions"
    QUERIES_ENDPOINT = "/v1/queries"
    GREETINGS_ENDPOINT = "/v1/greetings"
    PRESESSION_TRAY_ENDPOINT = "/v1/pre-session"
    QUESTION_SUGGESTIONS_ENDPOINT = "/v1/question-suggestions"
    PATIENTS_ENDPOINT = "/v1/patients"
    TOPICS_ENDPOINT = "/v1/topics"
    ROUTER_TAG = "assistant"

    def __init__(self,
                 environment: str,
                 auth_manager: AuthManagerBaseClass,
                 assistant_manager: AssistantManagerBaseClass):
        self._environment = environment
        self._auth_manager = auth_manager
        self._assistant_manager = assistant_manager
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def insert_new_session(body: model.SessionNotesInsert,
                                     request: Request,
                                     response: Response,
                                     datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                     datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._insert_new_session_internal(body=body,
                                                           request=request,
                                                           response=response,
                                                           datastore_access_token=datastore_access_token,
                                                           datastore_refresh_token=datastore_refresh_token,
                                                           authorization=authorization,
                                                           session_id=session_id)

        @self.router.put(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_session(body: model.SessionNotesUpdate,
                                 request: Request,
                                 response: Response,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_session_internal(body=body,
                                                       response=response,
                                                       request=request,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.delete(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_session(response: Response,
                                 request: Request,
                                 therapist_id: str = None,
                                 session_report_id: str = None,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_session_internal(therapist_id=therapist_id,
                                                       session_report_id=session_report_id,
                                                       response=response,
                                                       request=request,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.post(self.QUERIES_ENDPOINT, tags=[self.ROUTER_TAG])
        async def execute_assistant_query(query: model.AssistantQuery,
                                          response: Response,
                                          request: Request,
                                          datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                          datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._execute_assistant_query_internal(query=query,
                                                                request=request,
                                                                response=response,
                                                                datastore_access_token=datastore_access_token,
                                                                datastore_refresh_token=datastore_refresh_token,
                                                                authorization=authorization,
                                                                session_id=session_id)

        @self.router.get(self.GREETINGS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_greeting(response: Response,
                                 request: Request,
                                 client_tz_identifier: str = None,
                                 therapist_id: str = None,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_greeting_internal(response=response,
                                                       request=request,
                                                       client_tz_identifier=client_tz_identifier,
                                                       therapist_id=therapist_id,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.get(self.PRESESSION_TRAY_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_presession_tray(response: Response,
                                        request: Request,
                                        therapist_id: str = None,
                                        patient_id: str = None,
                                        briefing_configuration: model.BriefingConfiguration = model.BriefingConfiguration.UNDEFINED,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_presession_tray_internal(response=response,
                                                              request=request,
                                                              therapist_id=therapist_id,
                                                              patient_id=patient_id,
                                                              briefing_configuration=briefing_configuration,
                                                              datastore_access_token=datastore_access_token,
                                                              datastore_refresh_token=datastore_refresh_token,
                                                              authorization=authorization,
                                                              session_id=session_id)

        @self.router.get(self.QUESTION_SUGGESTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_question_suggestions(response: Response,
                                             request: Request,
                                             therapist_id: str = None,
                                             patient_id: str = None,
                                             datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                             datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                             authorization: Annotated[Union[str, None], Cookie()] = None,
                                             session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_question_suggestions_internal(response=response,
                                                                   request=request,
                                                                   therapist_id=therapist_id,
                                                                   patient_id=patient_id,
                                                                   datastore_access_token=datastore_access_token,
                                                                   datastore_refresh_token=datastore_refresh_token,
                                                                   authorization=authorization,
                                                                   session_id=session_id)

        @self.router.post(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def add_patient(response: Response,
                              request: Request,
                              body: model.PatientInsertPayload,
                              datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                              datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                              authorization: Annotated[Union[str, None], Cookie()] = None,
                              session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_patient_internal(response=response,
                                                    request=request,
                                                    body=body,
                                                    datastore_access_token=datastore_access_token,
                                                    datastore_refresh_token=datastore_refresh_token,
                                                    authorization=authorization,
                                                    session_id=session_id)

        @self.router.put(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_patient(response: Response,
                                 request: Request,
                                 body: model.PatientUpdatePayload,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_patient_internal(response=response,
                                                       request=request,
                                                       body=body,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.delete(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_patient(response: Response,
                                 request: Request,
                                 patient_id: str = None,
                                 therapist_id: str = None,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_patient_internal(response=response,
                                                       request=request,
                                                       patient_id=patient_id,
                                                       therapist_id=therapist_id,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.get(self.TOPICS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_frequent_topics(response: Response,
                                        request: Request,
                                        patient_id: str = None,
                                        therapist_id: str = None,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_frequent_topics_internal(response=response,
                                                              request=request,
                                                              patient_id=patient_id,
                                                              therapist_id=therapist_id,
                                                              datastore_access_token=datastore_access_token,
                                                              datastore_refresh_token=datastore_refresh_token,
                                                              authorization=authorization,
                                                              session_id=session_id)

    """
    Stores a new session report.

    Arguments:
    body – the incoming request json body.
    request – the incoming request object.
    response – the response model with which to create the final response.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _insert_new_session_internal(self,
                                           body: model.SessionNotesInsert,
                                           request: Request,
                                           response: Response,
                                           datastore_access_token: Annotated[Union[str, None], Cookie()],
                                           datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                           authorization: Annotated[Union[str, None], Cookie()],
                                           session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=body.therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                patient_id=body.patient_id,
                                therapist_id=body.therapist_id,
                                endpoint_name=self.SESSIONS_ENDPOINT,
                                method=logging.API_METHOD_POST,)

        try:
            assert body.source != model.SessionNotesSource.UNDEFINED, '''Invalid parameter 'undefined' for source.'''
            assert datetime_handler.is_valid_date(body.date), "Invalid date format. The expected format is mm-dd-yyyy"

            self._assistant_manager.process_new_session_data(auth_manager=self._auth_manager,
                                                             body=body,
                                                             datastore_access_token=datastore_access_token,
                                                             datastore_refresh_token=datastore_refresh_token,
                                                             session_id=session_id,
                                                             endpoint_name=self.SESSIONS_ENDPOINT,
                                                             method=logging.API_METHOD_POST,
                                                             environment=self._environment,
                                                             )

            logging.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    patient_id=body.patient_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            therapist_id=body.therapist_id,
                            patient_id=body.patient_id,
                            endpoint_name=self.SESSIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates a session report.

    Arguments:
    body – the incoming request body.
    request – the incoming request object.
    response – the response model with which to create the final response.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_session_internal(self,
                                       body: model.SessionNotesUpdate,
                                       request: Request,
                                       response: Response,
                                       datastore_access_token: Annotated[Union[str, None], Cookie()],
                                       datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=body.therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=body.therapist_id,
                                endpoint_name=self.SESSIONS_ENDPOINT,
                                method=logging.API_METHOD_PUT)

        try:
            assert datetime_handler.is_valid_date(body.date), "Received invalid date"
            assert body.source != model.SessionNotesSource.UNDEFINED, '''Invalid parameter 'undefined' for source.'''

            self._assistant_manager.update_session(auth_manager=self._auth_manager,
                                                   body=body,
                                                   datastore_access_token=datastore_access_token,
                                                   datastore_refresh_token=datastore_refresh_token,
                                                   environment=self._environment,
                                                   endpoint_name=self.SESSIONS_ENDPOINT,
                                                   method=logging.API_METHOD_PUT)

            logging.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_PUT)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            therapist_id=body.therapist_id,
                            endpoint_name=self.SESSIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_PUT)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes a session report.

    Arguments:
    therapist_id – the therapist id associated with the session report to be deleted.
    session_report_id – the id for the incoming session report.
    request – the incoming request object.
    response – the response model with which to create the final response.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_session_internal(self,
                                       therapist_id: str,
                                       session_report_id: str,
                                       request: Request,
                                       response: Response,
                                       datastore_access_token: Annotated[Union[str, None], Cookie()],
                                       datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=therapist_id,
                                session_report_id=session_report_id,
                                endpoint_name=self.SESSIONS_ENDPOINT,
                                method=logging.API_METHOD_DELETE)

        try:
            assert len(session_report_id or '') > 0, "Received invalid session_report_id"
            uuid.UUID(str(session_report_id))
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                              therapist_id=therapist_id,
                              session_report_id=session_report_id,
                              endpoint_name=self.SESSIONS_ENDPOINT,
                              error_code=status_code,
                              description=description,
                              method=logging.API_METHOD_DELETE)
            raise HTTPException(status_code=status_code,
                                detail=description)

        try:
            assert len(therapist_id or '') > 0, "Received invalid therapist_id param"
            self._assistant_manager.delete_session(auth_manager=self._auth_manager,
                                                   session_report_id=session_report_id,
                                                   datastore_access_token=datastore_access_token,
                                                   datastore_refresh_token=datastore_refresh_token)

            logging.log_api_response(session_id=session_id,
                                     therapist_id=therapist_id,
                                     session_report_id=session_report_id,
                                     endpoint_name=self.SESSIONS_ENDPOINT,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_DELETE)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            session_report_id=session_report_id,
                            endpoint_name=self.SESSIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_DELETE)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Executes a query to our assistant system.
    Returns the query response.

    Arguments:
    query – the query that will be executed.
    request – the incoming request object.
    response – the response model with which to create the final response.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _execute_assistant_query_internal(self,
                                                query: model.AssistantQuery,
                                                request: Request,
                                                response: Response,
                                                datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                authorization: Annotated[Union[str, None], Cookie()],
                                                session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=query.therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=query.therapist_id,
                                patient_id=query.patient_id,
                                endpoint_name=self.QUERIES_ENDPOINT,
                                method=logging.API_METHOD_POST)

        try:
            assert len(query.therapist_id or '') > 0, "Invalid therapist_id in payload"
            assert len(query.patient_id or '') > 0, "Invalid patient_id in payload"
            assert len(query.text or '') > 0, "Invalid text in payload"

            response = self._assistant_manager.query_session(auth_manager=self._auth_manager,
                                                             query=query,
                                                             session_id=session_id,
                                                             api_method=logging.API_METHOD_POST,
                                                             endpoint_name=self.QUERIES_ENDPOINT,
                                                             environment=self._environment,
                                                             datastore_access_token=datastore_access_token,
                                                             datastore_refresh_token=datastore_refresh_token)

            logging.log_api_response(session_id=session_id,
                            therapist_id=query.therapist_id,
                            patient_id=query.patient_id,
                            endpoint_name=self.QUERIES_ENDPOINT,
                            http_status_code=status.HTTP_200_OK,
                            method=logging.API_METHOD_POST)
            return response
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            patient_id=query.patient_id,
                            endpoint_name=self.QUERIES_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Returns a new greeting to the user.

    Arguments:
    response – the response model used for the final response that will be returned.
    request – the incoming request object.
    client_tz_identifier – the timezone identifier associated with the client.
    therapist_id – the therapist id associated with the user.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _fetch_greeting_internal(self,
                                       response: Response,
                                       request: Request,
                                       client_tz_identifier: str,
                                       therapist_id: str,
                                       datastore_access_token: Annotated[Union[str, None], Cookie()],
                                       datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logs_description = ''.join(['tz_identifier:', client_tz_identifier])
        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_GET,
                                therapist_id=therapist_id,
                                endpoint_name=self.GREETINGS_ENDPOINT,
                                description=logs_description)

        try:
            assert general_utilities.is_valid_timezone_identifier(client_tz_identifier), "Invalid timezone identifier parameter"

            result = self._assistant_manager.fetch_todays_greeting(client_tz_identifier=client_tz_identifier,
                                                                   therapist_id=therapist_id,
                                                                   session_id=session_id,
                                                                   endpoint_name=self.GREETINGS_ENDPOINT,
                                                                   api_method=logging.API_METHOD_GET,
                                                                   environment=self._environment,
                                                                   auth_manager=self._auth_manager,
                                                                   datastore_access_token=datastore_access_token,
                                                                   datastore_refresh_token=datastore_refresh_token)

            logging.log_api_response(session_id=session_id,
                                    endpoint_name=self.GREETINGS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    http_status_code=status.HTTP_200_OK,
                                    description=logs_description,
                                    method=logging.API_METHOD_GET)

            return {"message": result}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            endpoint_name=self.GREETINGS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_GET)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Returns a pre-session tray.

    Arguments:
    response – the response model used for the final response that will be returned.
    request – the incoming request object.
    therapist_id – the id associated with the user.
    patient_id – the id associated with the patient whose presession tray will be fetched.
    briefing_configuration – the summary configuration.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _fetch_presession_tray_internal(self,
                                              response: Response,
                                              request: Request,
                                              therapist_id: str,
                                              patient_id: str,
                                              briefing_configuration: model.BriefingConfiguration,
                                              datastore_access_token: Annotated[Union[str, None], Cookie()],
                                              datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                              authorization: Annotated[Union[str, None], Cookie()],
                                              session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_GET,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=self.PRESESSION_TRAY_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Missing therapist_id param"
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert briefing_configuration != model.BriefingConfiguration.UNDEFINED, '''Invalid parameter 'undefined' for briefing_configuration.'''

            json_response = self._assistant_manager.create_patient_summary(patient_id=patient_id,
                                                                           therapist_id=therapist_id,
                                                                           environment=self._environment,
                                                                           session_id=session_id,
                                                                           endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                                                           api_method=logging.API_METHOD_GET,
                                                                           auth_manager=self._auth_manager,
                                                                           configuration=briefing_configuration,
                                                                           datastore_access_token=datastore_access_token,
                                                                           datastore_refresh_token=datastore_refresh_token)

            logging.log_api_response(session_id=session_id,
                                     endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                     therapist_id=therapist_id,
                                     patient_id=patient_id,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_GET)
            return json_response
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_GET)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Returns a set of question suggestions based on the incoming patient context.

    Arguments:
    response – the response model used for the final response that will be returned.
    request – the incoming request object.
    therapist_id – the id associated with the therapist user.
    patient_id – the id associated with the patient whose sessions will be used to fetch suggested questions.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _fetch_question_suggestions_internal(self,
                                                   response: Response,
                                                   request: Request,
                                                   therapist_id: str,
                                                   patient_id: str,
                                                   datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                   datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                   authorization: Annotated[Union[str, None], Cookie()],
                                                   session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_GET,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            json_questions = self._assistant_manager.fetch_question_suggestions(therapist_id=therapist_id,
                                                                                patient_id=patient_id,
                                                                                auth_manager=self._auth_manager,
                                                                                environment=self._environment,
                                                                                session_id=session_id,
                                                                                endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                                                                api_method=logging.API_METHOD_GET,
                                                                                datastore_access_token=datastore_access_token,
                                                                                datastore_refresh_token=datastore_refresh_token)

            logging.log_api_response(session_id=session_id,
                                     endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                     therapist_id=therapist_id,
                                     patient_id=patient_id,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_GET)

            return json_questions
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_GET)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Adds a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    body – the body associated with the request.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _add_patient_internal(self,
                                    response: Response,
                                    request: Request,
                                    body: model.PatientInsertPayload,
                                    datastore_access_token: Annotated[Union[str, None], Cookie()],
                                    datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                    authorization: Annotated[Union[str, None], Cookie()],
                                    session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=body.therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_POST,
                                endpoint_name=self.PATIENTS_ENDPOINT,
                                therapist_id=body.therapist_id)

        try:
            assert body.consentment_channel != model.PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert body.gender != model.Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date format. The expected format is mm-dd-yyyy"

            datastore_client: Client = self._auth_manager.datastore_user_instance(datastore_access_token,
                                                                                  datastore_refresh_token)
            response = datastore_client.table('patients').insert({
                "first_name": body.first_name,
                "middle_name": body.middle_name,
                "last_name": body.last_name,
                "birth_date": body.birth_date,
                "email": body.email,
                "gender": body.gender.value,
                "phone_number": body.phone_number,
                "consentment_channel": body.consentment_channel.value,
            }).execute()
            patient_id = response.dict()['data'][0]['id']

            logging.log_api_response(session_id=session_id,
                                     method=logging.API_METHOD_POST,
                                     endpoint_name=self.PATIENTS_ENDPOINT,
                                     therapist_id=body.therapist_id,
                                     patient_id=patient_id,
                                     http_status_code=status.HTTP_200_OK)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                              endpoint_name=self.PATIENTS_ENDPOINT,
                              error_code=status_code,
                              therapist_id=body.therapist_id,
                              description=description,
                              method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    body – the body associated with the request.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_patient_internal(self,
                                       response: Response,
                                       request: Request,
                                       body: model.PatientUpdatePayload,
                                       datastore_access_token: Annotated[Union[str, None], Cookie()],
                                       datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=body.therapist_id,
                                                     response=response,
                                                     request=request)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_PUT,
                                endpoint_name=self.PATIENTS_ENDPOINT,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id)

        try:
            assert len(body.patient_id or '') > 0, "Missing patient_id param in payload"
            assert body.consentment_channel != model.PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert body.gender != model.Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date format. The expected format is mm-dd-yyyy"

            datastore_client: Client = self._auth_manager.datastore_user_instance(datastore_access_token,
                                                                                  datastore_refresh_token)
            datastore_client.table('patients').update({
                "first_name": body.first_name,
                "middle_name": body.middle_name,
                "last_name": body.last_name,
                "birth_date": body.birth_date,
                "email": body.email,
                "gender": body.gender.value,
                "phone_number": body.phone_number,
                "consentment_channel": body.consentment_channel.value,
            }).eq('id', body.patient_id).execute()

            logging.log_api_response(session_id=session_id,
                                     method=logging.API_METHOD_PUT,
                                     endpoint_name=self.PATIENTS_ENDPOINT,
                                     therapist_id=body.therapist_id,
                                     patient_id=body.patient_id,
                                     http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                              endpoint_name=self.PATIENTS_ENDPOINT,
                              error_code=status_code,
                              therapist_id=body.therapist_id,
                              patient_id=body.patient_id,
                              description=description,
                              method=logging.API_METHOD_PUT)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    patient_id – the id for the patient to be deleted.
    therapist_id – the therapist id associated with the patient to be deleted.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_patient_internal(self,
                                       response: Response,
                                       request: Request,
                                       patient_id: str,
                                       therapist_id: str,
                                       datastore_access_token: Annotated[Union[str, None], Cookie()],
                                       datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response,
                                                     request=request)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_DELETE,
                                endpoint_name=self.PATIENTS_ENDPOINT,
                                therapist_id=therapist_id,
                                patient_id=patient_id,)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            datastore_client: Client = self._auth_manager.datastore_user_instance(datastore_access_token,
                                                                                  datastore_refresh_token)
            delete_response = datastore_client.table('patients').delete().eq('id', patient_id).execute().dict()
            assert len(delete_response['data']) > 0, "No patient found with the incoming patient_id"

            self._assistant_manager.delete_all_sessions_for_patient(therapist_id=therapist_id, patient_id=patient_id)

            logging.log_api_response(session_id=session_id,
                                     method=logging.API_METHOD_DELETE,
                                     endpoint_name=self.PATIENTS_ENDPOINT,
                                     therapist_id=therapist_id,
                                     patient_id=patient_id,
                                     http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                              endpoint_name=self.PATIENTS_ENDPOINT,
                              error_code=status_code,
                              therapist_id=therapist_id,
                              patient_id=patient_id,
                              description=description,
                              method=logging.API_METHOD_DELETE)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Returns a set of topics (along with frequency percentages) that the incoming patient_id is associated with.

    Arguments:
    response – the response model used for the final response that will be returned.
    request – the incoming request object.
    therapist_id – the id associated with the therapist user.
    patient_id – the id associated with the patient whose sessions will be used to fetch suggested questions.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _fetch_frequent_topics_internal(self,
                                             response: Response,
                                             request: Request,
                                             therapist_id: str,
                                             patient_id: str,
                                             datastore_access_token: Annotated[Union[str, None], Cookie()],
                                             datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                             authorization: Annotated[Union[str, None], Cookie()],
                                             session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_GET,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=self.TOPICS_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            json_topics = self._assistant_manager.fetch_frequent_topics(therapist_id=therapist_id,
                                                                        patient_id=patient_id,
                                                                        auth_manager=self._auth_manager,
                                                                        environment=self._environment,
                                                                        session_id=session_id,
                                                                        endpoint_name=self.TOPICS_ENDPOINT,
                                                                        api_method=logging.API_METHOD_GET,
                                                                        datastore_access_token=datastore_access_token,
                                                                        datastore_refresh_token=datastore_refresh_token)

            logging.log_api_response(session_id=session_id,
                                     endpoint_name=self.TOPICS_ENDPOINT,
                                     therapist_id=therapist_id,
                                     patient_id=patient_id,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_GET)

            return json_topics
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logging.log_error(session_id=session_id,
                            endpoint_name=self.TOPICS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_GET)
            raise HTTPException(status_code=status_code,
                                detail=description)
