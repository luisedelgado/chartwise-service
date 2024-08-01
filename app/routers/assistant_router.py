import json, uuid

from fastapi import (APIRouter,
                     Cookie,
                     HTTPException,
                     Request,
                     Response,
                     status)
from fastapi.responses import StreamingResponse
from typing import Annotated, Union

from ..api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ..internal import security
from ..internal.logging import Logger
from ..internal.model import (AssistantQuery,
                              Gender,
                              PatientConsentmentChannel,
                              PatientInsertPayload,
                              PatientUpdatePayload,
                              SessionNotesInsert,
                              SessionNotesSource,
                              SessionNotesTemplate,
                              SessionNotesUpdate,
                              TemplatePayload)
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.implementations.assistant_manager import AssistantManager
from ..managers.implementations.auth_manager import AuthManager
from ..managers.implementations.openai_manager import OpenAIManager

class AssistantRouter:

    SESSIONS_ENDPOINT = "/v1/sessions"
    QUERIES_ENDPOINT = "/v1/queries"
    GREETINGS_ENDPOINT = "/v1/greetings"
    PRESESSION_TRAY_ENDPOINT = "/v1/pre-session"
    QUESTION_SUGGESTIONS_ENDPOINT = "/v1/question-suggestions"
    PATIENTS_ENDPOINT = "/v1/patients"
    TOPICS_ENDPOINT = "/v1/topics"
    TEMPLATES_ENDPOINT = "/v1/templates"
    ROUTER_TAG = "assistant"

    def __init__(self,
                 environment: str,
                 auth_manager: AuthManager,
                 assistant_manager: AssistantManager,
                 openai_manager: OpenAIManager,
                 supabase_manager_factory: SupabaseFactoryBaseClass):
        self._environment = environment
        self._auth_manager = auth_manager
        self._assistant_manager = assistant_manager
        self._openai_manager = openai_manager
        self._supabase_manager_factory = supabase_manager_factory
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def insert_new_session(body: SessionNotesInsert,
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
        async def update_session(body: SessionNotesUpdate,
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
        async def execute_assistant_query(query: AssistantQuery,
                                          response: Response,
                                          request: Request,
                                          datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                          datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            if not self._auth_manager.access_token_is_valid(authorization):
                raise security.AUTH_TOKEN_EXPIRED_ERROR

            if datastore_access_token is None or datastore_refresh_token is None:
                raise security.DATASTORE_TOKENS_ERROR

            try:
                await self._auth_manager.refresh_session(user_id=query.therapist_id,
                                                         request=request,
                                                         response=response,
                                                         supabase_manager_factory=self._supabase_manager_factory)
            except Exception as e:
                status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
                raise HTTPException(status_code=status_code, detail=str(e))

            try:
                assert len(query.therapist_id or '') > 0, "Invalid therapist_id in payload"
                assert len(query.patient_id or '') > 0, "Invalid patient_id in payload"
                assert len(query.text or '') > 0, "Invalid text in payload"
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

            return StreamingResponse(self._execute_assistant_query_internal(query=query,
                                                                            datastore_access_token=datastore_access_token,
                                                                            datastore_refresh_token=datastore_refresh_token,
                                                                            session_id=session_id),
                                     media_type="text/plain")

        @self.router.get(self.GREETINGS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_greeting(response: Response,
                                 request: Request,
                                 client_timezone_identifier: str = None,
                                 therapist_id: str = None,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_greeting_internal(response=response,
                                                       request=request,
                                                       client_tz_identifier=client_timezone_identifier,
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
                                        datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_presession_tray_internal(response=response,
                                                              request=request,
                                                              therapist_id=therapist_id,
                                                              patient_id=patient_id,
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
                              body: PatientInsertPayload,
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
                                 body: PatientUpdatePayload,
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

        @self.router.post(self.TEMPLATES_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transform_session_with_template(response: Response,
                                                  request: Request,
                                                  body: TemplatePayload,
                                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transform_session_with_template_internal(response=response,
                                                                        request=request,
                                                                        therapist_id=body.therapist_id,
                                                                        session_notes_text=body.session_notes_text,
                                                                        template=body.template,
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
                                           body: SessionNotesInsert,
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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(session_id=session_id,
                               patient_id=body.patient_id,
                               therapist_id=body.therapist_id,
                               endpoint_name=self.SESSIONS_ENDPOINT,
                               method=post_api_method,)

        try:
            assert body.source != SessionNotesSource.UNDEFINED, '''Invalid parameter 'undefined' for source.'''
            assert general_utilities.is_valid_timezone_identifier(body.client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=body.date,
                                                  tz_identifier=body.client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            session_notes_id = await self._assistant_manager.process_new_session_data(auth_manager=self._auth_manager,
                                                                                      body=body,
                                                                                      session_id=session_id,
                                                                                      openai_manager=self._openai_manager,
                                                                                      supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    patient_id=body.patient_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"session_report_id": session_notes_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             therapist_id=body.therapist_id,
                             patient_id=body.patient_id,
                             endpoint_name=self.SESSIONS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
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
                                       body: SessionNotesUpdate,
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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        put_api_method = logger.API_METHOD_PUT
        logger.log_api_request(session_id=session_id,
                               therapist_id=body.therapist_id,
                               endpoint_name=self.SESSIONS_ENDPOINT,
                               method=put_api_method)

        try:
            assert general_utilities.is_valid_timezone_identifier(body.client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=body.date,
                                                  tz_identifier=body.client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert body.source != SessionNotesSource.UNDEFINED, '''Invalid parameter 'undefined' for source.'''

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            await self._assistant_manager.update_session(auth_manager=self._auth_manager,
                                                         body=body,
                                                         session_id=session_id,
                                                         openai_manager=self._openai_manager,
                                                         supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=put_api_method)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             therapist_id=body.therapist_id,
                             endpoint_name=self.SESSIONS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=put_api_method)
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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        delete_api_method = logger.API_METHOD_DELETE
        logger.log_api_request(session_id=session_id,
                               therapist_id=therapist_id,
                               session_report_id=session_report_id,
                               endpoint_name=self.SESSIONS_ENDPOINT,
                               method=delete_api_method)

        try:
            assert len(session_report_id or '') > 0, "Received invalid session_report_id"
            uuid.UUID(str(session_report_id))
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             therapist_id=therapist_id,
                             session_report_id=session_report_id,
                             endpoint_name=self.SESSIONS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=delete_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

        try:
            assert len(therapist_id or '') > 0, "Received invalid therapist_id param"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            self._assistant_manager.delete_session(therapist_id=therapist_id,
                                                   session_report_id=session_report_id,
                                                   supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    therapist_id=therapist_id,
                                    session_report_id=session_report_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=delete_api_method)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             session_report_id=session_report_id,
                             endpoint_name=self.SESSIONS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=delete_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Executes a query to our assistant system.
    Returns the query response.

    Arguments:
    query – the query that will be executed.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _execute_assistant_query_internal(self,
                                                query: AssistantQuery,
                                                datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                session_id: Annotated[Union[str, None], Cookie()]):
        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(session_id=session_id,
                               therapist_id=query.therapist_id,
                               patient_id=query.patient_id,
                               endpoint_name=self.QUERIES_ENDPOINT,
                               method=post_api_method)

        try:
            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            async for part in self._assistant_manager.query_session(auth_manager=self._auth_manager,
                                                                    query=query,
                                                                    session_id=session_id,
                                                                    api_method=post_api_method,
                                                                    endpoint_name=self.QUERIES_ENDPOINT,
                                                                    environment=self._environment,
                                                                    openai_manager=self._openai_manager,
                                                                    supabase_manager=supabase_manager):
                yield part

            logger.log_api_response(session_id=session_id,
                                    therapist_id=query.therapist_id,
                                    patient_id=query.patient_id,
                                    endpoint_name=self.QUERIES_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)
        except Exception as e:
            yield json.dumps({"error": str(e)})
            logger.log_error(session_id=session_id,
                             patient_id=query.patient_id,
                             endpoint_name=self.QUERIES_ENDPOINT,
                             error_code=general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST),
                             description=str(e),
                             method=post_api_method)

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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        logs_description = ''.join(['tz_identifier:', client_tz_identifier])
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               endpoint_name=self.GREETINGS_ENDPOINT,
                               description=logs_description)

        try:
            assert general_utilities.is_valid_timezone_identifier(client_tz_identifier), "Invalid timezone identifier parameter"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            result = await self._assistant_manager.fetch_todays_greeting(client_tz_identifier=client_tz_identifier,
                                                                         therapist_id=therapist_id,
                                                                         session_id=session_id,
                                                                         endpoint_name=self.GREETINGS_ENDPOINT,
                                                                         api_method=get_api_method,
                                                                         environment=self._environment,
                                                                         auth_manager=self._auth_manager,
                                                                         openai_manager=self._openai_manager,
                                                                         supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    endpoint_name=self.GREETINGS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    http_status_code=status.HTTP_200_OK,
                                    description=logs_description,
                                    method=get_api_method)

            return {"message": result}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.GREETINGS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=get_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Returns a pre-session tray.

    Arguments:
    response – the response model used for the final response that will be returned.
    request – the incoming request object.
    therapist_id – the id associated with the user.
    patient_id – the id associated with the patient whose presession tray will be fetched.
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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.PRESESSION_TRAY_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Missing therapist_id param"
            assert len(patient_id or '') > 0, "Missing patient_id param"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            json_response = await self._assistant_manager.create_patient_summary(patient_id=patient_id,
                                                                                 therapist_id=therapist_id,
                                                                                 environment=self._environment,
                                                                                 session_id=session_id,
                                                                                 endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                                                                 api_method=get_api_method,
                                                                                 auth_manager=self._auth_manager,
                                                                                 openai_manager=self._openai_manager,
                                                                                 supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)
            return json_response
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=get_api_method)
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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            json_questions = await self._assistant_manager.fetch_question_suggestions(therapist_id=therapist_id,
                                                                                      patient_id=patient_id,
                                                                                      auth_manager=self._auth_manager,
                                                                                      environment=self._environment,
                                                                                      session_id=session_id,
                                                                                      endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                                                                      api_method=get_api_method,
                                                                                      openai_manager=self._openai_manager,
                                                                                      supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)

            return json_questions
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=get_api_method)
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
                                    body: PatientInsertPayload,
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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(session_id=session_id,
                               method=post_api_method,
                               endpoint_name=self.PATIENTS_ENDPOINT,
                               therapist_id=body.therapist_id)

        try:
            assert body.consentment_channel != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert body.gender != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            patient_id = await self._assistant_manager.add_patient(auth_manager=self._auth_manager,
                                                                   payload=body,
                                                                   session_id=session_id,
                                                                   openai_manager=self._openai_manager,
                                                                   supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    method=post_api_method,
                                    endpoint_name=self.PATIENTS_ENDPOINT,
                                    therapist_id=body.therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK)

            return {"patient_id": patient_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.PATIENTS_ENDPOINT,
                             error_code=status_code,
                             therapist_id=body.therapist_id,
                             description=description,
                             method=post_api_method)
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
                                       body: PatientUpdatePayload,
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
                                                     request=request,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        put_api_method = logger.API_METHOD_PUT
        logger.log_api_request(session_id=session_id,
                               method=put_api_method,
                               endpoint_name=self.PATIENTS_ENDPOINT,
                               therapist_id=body.therapist_id,
                               patient_id=body.patient_id)

        try:
            assert len(body.patient_id or '') > 0, "Missing patient_id param in payload"
            assert body.consentment_channel != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert body.gender != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            await self._assistant_manager.update_patient(auth_manager=self._auth_manager,
                                                         payload=body,
                                                         session_id=session_id,
                                                         openai_manager=self._openai_manager,
                                                         supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    method=put_api_method,
                                    endpoint_name=self.PATIENTS_ENDPOINT,
                                    therapist_id=body.therapist_id,
                                    patient_id=body.patient_id,
                                    http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.PATIENTS_ENDPOINT,
                             error_code=status_code,
                             therapist_id=body.therapist_id,
                             patient_id=body.patient_id,
                             description=description,
                             method=put_api_method)
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
                                                     request=request,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        delete_api_method = logger.API_METHOD_DELETE
        logger.log_api_request(session_id=session_id,
                               method=delete_api_method,
                               endpoint_name=self.PATIENTS_ENDPOINT,
                               therapist_id=therapist_id,
                               patient_id=patient_id,)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)

            patient_query = supabase_manager.select(fields="*",
                                                    filters={
                                                        'therapist_id': therapist_id,
                                                        'id': patient_id
                                                    },
                                                    table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            # Cascading will take care of deleting the session notes in Supabase.
            delete_result = supabase_manager.delete(table_name="patients",
                                                    filters={
                                                        'id': patient_id
                                                    })
            assert len(delete_result.dict()['data']) > 0, "No patient found with the incoming patient_id"

            self._assistant_manager.delete_all_data_for_patient(therapist_id=therapist_id, patient_id=patient_id)

            logger.log_api_response(session_id=session_id,
                                    method=delete_api_method,
                                    endpoint_name=self.PATIENTS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.PATIENTS_ENDPOINT,
                             error_code=status_code,
                             therapist_id=therapist_id,
                             patient_id=patient_id,
                             description=description,
                             method=delete_api_method)
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
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.TOPICS_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            json_topics = await self._assistant_manager.fetch_frequent_topics(therapist_id=therapist_id,
                                                                              patient_id=patient_id,
                                                                              auth_manager=self._auth_manager,
                                                                              environment=self._environment,
                                                                              session_id=session_id,
                                                                              endpoint_name=self.TOPICS_ENDPOINT,
                                                                              api_method=get_api_method,
                                                                              openai_manager=self._openai_manager,
                                                                              supabase_manager=supabase_manager)

            logger.log_api_response(session_id=session_id,
                                    endpoint_name=self.TOPICS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)

            return json_topics
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.TOPICS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=get_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Adapts an incoming set of session notes into the SOAP format and returns the result.

    Arguments:
    response – the response model used for the final response that will be returned.
    request – the incoming request object.
    therapist_id – the id associated with the therapist user.
    session_notes_text – the session notes to be adapted into SOAP.
    template – the template to be applied.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _transform_session_with_template_internal(self,
                                                        response: Response,
                                                        request: Request,
                                                        therapist_id: str,
                                                        session_notes_text: str,
                                                        template: SessionNotesTemplate,
                                                        authorization: Annotated[Union[str, None], Cookie()],
                                                        session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_manager_factory=self._supabase_manager_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_manager_factory=self._supabase_manager_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(session_id=session_id,
                               method=post_api_method,
                               endpoint_name=self.TEMPLATES_ENDPOINT,
                               therapist_id=therapist_id,)

        try:
            assert len(session_notes_text or '') > 0, "Empty session_notes_text param"
            assert len(therapist_id or '') > 0, "Empty therapist_id param"
            assert template != SessionNotesTemplate.FREE_FORM, "free_form is not a template that can be applied"

            soap_notes = await self._assistant_manager.adapt_session_notes_to_soap(auth_manager=self._auth_manager,
                                                                                   openai_manager=self._openai_manager,
                                                                                   therapist_id=therapist_id,
                                                                                   session_id=session_id,
                                                                                   session_notes_text=session_notes_text)
            logger.log_api_response(session_id=session_id,
                                    endpoint_name=self.TEMPLATES_ENDPOINT,
                                    therapist_id=therapist_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"soap_notes": soap_notes}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.TEMPLATES_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)
