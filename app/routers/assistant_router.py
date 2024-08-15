import uuid

from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     HTTPException,
                     Request,
                     Response,
                     status)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Annotated, AsyncIterable, Union

from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.templates import SessionNotesTemplate
from ..internal import security
from ..internal.logging import Logger
from ..internal.router_dependencies import RouterDependencies
from ..internal.schemas import Gender
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import (AssistantManager,
                                          AssistantQuery,
                                          PatientConsentmentChannel,
                                          PatientInsertPayload,
                                          PatientUpdatePayload,
                                          SessionNotesInsert,
                                          SessionNotesSource,
                                          SessionNotesUpdate)
from ..managers.auth_manager import AuthManager

class TemplatePayload(BaseModel):
    session_notes_text: str
    template: SessionNotesTemplate = SessionNotesTemplate.SOAP

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
                 router_dependencies: RouterDependencies):
        self._environment = environment
        self._auth_manager = auth_manager
        self._assistant_manager = assistant_manager
        self._openai_client = router_dependencies.openai_client
        self._pinecone_client = router_dependencies.pinecone_client
        self._supabase_client_factory = router_dependencies.supabase_client_factory
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
                                     background_tasks: BackgroundTasks,
                                     datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                     datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._insert_new_session_internal(body=body,
                                                           background_tasks=background_tasks,
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
                                 background_tasks: BackgroundTasks,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_session_internal(body=body,
                                                       response=response,
                                                       request=request,
                                                       background_tasks=background_tasks,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.delete(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_session(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 therapist_id: str = None,
                                 session_report_id: str = None,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_session_internal(therapist_id=therapist_id,
                                                       session_report_id=session_report_id,
                                                       background_tasks=background_tasks,
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
                                          background_tasks: BackgroundTasks,
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
                                                         supabase_client_factory=self._supabase_client_factory)
            except Exception as e:
                status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
                raise HTTPException(status_code=status_code, detail=str(e))

            try:
                assert len(query.therapist_id or '') > 0, "Invalid therapist_id in payload"
                assert len(query.patient_id or '') > 0, "Invalid patient_id in payload"
                assert len(query.text or '') > 0, "Invalid text in payload"

                supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                     refresh_token=datastore_refresh_token)
                language_code_query = supabase_client.select(fields="*",
                                                             filters={
                                                                 'id': query.therapist_id
                                                             },
                                                             table_name="therapists")
                assert (0 != len((language_code_query).data)), "Did not find therapist data."
                language_code = language_code_query.dict()['data'][0]['language_preference']
                return StreamingResponse(self._execute_assistant_query_internal(query=query,
                                                                                background_tasks=background_tasks,
                                                                                supabase_client=supabase_client,
                                                                                language_code=language_code,
                                                                                session_id=session_id),
                                         media_type="text/event-stream")
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self.router.get(self.GREETINGS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_greeting(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 client_timezone_identifier: str = None,
                                 therapist_id: str = None,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_greeting_internal(response=response,
                                                       request=request,
                                                       background_tasks=background_tasks,
                                                       client_tz_identifier=client_timezone_identifier,
                                                       therapist_id=therapist_id,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.get(self.PRESESSION_TRAY_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_presession_tray(response: Response,
                                        request: Request,
                                        background_tasks: BackgroundTasks,
                                        therapist_id: str = None,
                                        patient_id: str = None,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_presession_tray_internal(response=response,
                                                              request=request,
                                                              background_tasks=background_tasks,
                                                              therapist_id=therapist_id,
                                                              patient_id=patient_id,
                                                              datastore_access_token=datastore_access_token,
                                                              datastore_refresh_token=datastore_refresh_token,
                                                              authorization=authorization,
                                                              session_id=session_id)

        @self.router.get(self.QUESTION_SUGGESTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_question_suggestions(response: Response,
                                             request: Request,
                                             background_tasks: BackgroundTasks,
                                             therapist_id: str = None,
                                             patient_id: str = None,
                                             datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                             datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                             authorization: Annotated[Union[str, None], Cookie()] = None,
                                             session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_question_suggestions_internal(response=response,
                                                                   request=request,
                                                                   background_tasks=background_tasks,
                                                                   therapist_id=therapist_id,
                                                                   patient_id=patient_id,
                                                                   datastore_access_token=datastore_access_token,
                                                                   datastore_refresh_token=datastore_refresh_token,
                                                                   authorization=authorization,
                                                                   session_id=session_id)

        @self.router.post(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def add_patient(response: Response,
                              request: Request,
                              background_tasks: BackgroundTasks,
                              body: PatientInsertPayload,
                              datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                              datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                              authorization: Annotated[Union[str, None], Cookie()] = None,
                              session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_patient_internal(response=response,
                                                    request=request,
                                                    background_tasks=background_tasks,
                                                    body=body,
                                                    datastore_access_token=datastore_access_token,
                                                    datastore_refresh_token=datastore_refresh_token,
                                                    authorization=authorization,
                                                    session_id=session_id)

        @self.router.put(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_patient(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 body: PatientUpdatePayload,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_patient_internal(response=response,
                                                       request=request,
                                                       body=body,
                                                       background_tasks=background_tasks,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.delete(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_patient(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 patient_id: str = None,
                                 therapist_id: str = None,
                                 datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_patient_internal(response=response,
                                                       request=request,
                                                       background_tasks=background_tasks,
                                                       patient_id=patient_id,
                                                       therapist_id=therapist_id,
                                                       datastore_access_token=datastore_access_token,
                                                       datastore_refresh_token=datastore_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.get(self.TOPICS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_frequent_topics(response: Response,
                                        request: Request,
                                        background_tasks: BackgroundTasks,
                                        patient_id: str = None,
                                        therapist_id: str = None,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_frequent_topics_internal(response=response,
                                                              request=request,
                                                              background_tasks=background_tasks,
                                                              patient_id=patient_id,
                                                              therapist_id=therapist_id,
                                                              datastore_access_token=datastore_access_token,
                                                              datastore_refresh_token=datastore_refresh_token,
                                                              authorization=authorization,
                                                              session_id=session_id)

        @self.router.post(self.TEMPLATES_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transform_session_with_template(response: Response,
                                                  request: Request,
                                                  background_tasks: BackgroundTasks,
                                                  body: TemplatePayload,
                                                  datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                                  datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transform_session_with_template_internal(response=response,
                                                                        request=request,
                                                                        background_tasks=background_tasks,
                                                                        session_notes_text=body.session_notes_text,
                                                                        template=body.template,
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
    background_tasks – object for scheduling concurrent tasks.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _insert_new_session_internal(self,
                                           body: SessionNotesInsert,
                                           request: Request,
                                           response: Response,
                                           background_tasks: BackgroundTasks,
                                           datastore_access_token: Annotated[Union[str, None], Cookie()],
                                           datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                           authorization: Annotated[Union[str, None], Cookie()],
                                           session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               patient_id=body.patient_id,
                               therapist_id=therapist_id,
                               endpoint_name=self.SESSIONS_ENDPOINT,
                               method=post_api_method,)

        try:
            assert body.source != SessionNotesSource.UNDEFINED, '''Invalid parameter 'undefined' for source.'''
            assert general_utilities.is_valid_timezone_identifier(body.client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=body.session_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT,
                                                  tz_identifier=body.client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            session_notes_id = await self._assistant_manager.process_new_session_data(auth_manager=self._auth_manager,
                                                                                      body=body,
                                                                                      session_id=session_id,
                                                                                      therapist_id=therapist_id,
                                                                                      openai_client=self._openai_client,
                                                                                      supabase_client=supabase_client,
                                                                                      pinecone_client=self._pinecone_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=body.patient_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"session_report_id": session_notes_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_session_internal(self,
                                       body: SessionNotesUpdate,
                                       request: Request,
                                       response: Response,
                                       background_tasks: BackgroundTasks,
                                       datastore_access_token: Annotated[Union[str, None], Cookie()],
                                       datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        put_api_method = logger.API_METHOD_PUT
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               therapist_id=therapist_id,
                               endpoint_name=self.SESSIONS_ENDPOINT,
                               method=put_api_method)

        try:
            body = body.dict(exclude_unset=True)

            assert 'client_timezone_identifier' not in body or general_utilities.is_valid_timezone_identifier(body['client_timezone_identifier']), "Invalid timezone identifier parameter"
            assert 'session_date' not in body or datetime_handler.is_valid_date(date_input=body['session_date'],
                                                                                incoming_date_format=datetime_handler.DATE_FORMAT,
                                                                                tz_identifier=body['client_timezone_identifier']), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert 'source' not in body or body['source'] != SessionNotesSource.UNDEFINED, '''Invalid parameter 'undefined' for source.'''

            await self._assistant_manager.update_session(auth_manager=self._auth_manager,
                                                         filtered_body=body,
                                                         session_id=session_id,
                                                         openai_client=self._openai_client,
                                                         supabase_client=supabase_client,
                                                         pinecone_client=self._pinecone_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    session_report_id=body['id'],
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=put_api_method)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             session_report_id=body['id'],
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
    background_tasks – object for scheduling concurrent tasks.
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
                                       background_tasks: BackgroundTasks,
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
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        delete_api_method = logger.API_METHOD_DELETE
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
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
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            self._assistant_manager.delete_session(therapist_id=therapist_id,
                                                   session_report_id=session_report_id,
                                                   supabase_client=supabase_client,
                                                   pinecone_client=self._pinecone_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    session_report_id=session_report_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=delete_api_method)

            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
    query – the query that will be executed.
    supabase_client – the supabase client to be used internally.
    language_code – the language code associated with the request.
    session_id – the session_id cookie, if exists.
    """
    async def _execute_assistant_query_internal(self,
                                                background_tasks: BackgroundTasks,
                                                query: AssistantQuery,
                                                supabase_client: SupabaseBaseClass,
                                                language_code: str,
                                                session_id: Annotated[Union[str, None], Cookie()]) -> AsyncIterable[str]:
        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               therapist_id=query.therapist_id,
                               patient_id=query.patient_id,
                               endpoint_name=self.QUERIES_ENDPOINT,
                               method=post_api_method)

        try:
            strings_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'id': self._default_streaming_error_message_id(language_code)
                                                   },
                                                   table_name="user_interface_strings")
            assert (0 != len((strings_query).data))
            default_error_string = strings_query.dict()['data'][0]['value']

            async for part in self._assistant_manager.query_session(auth_manager=self._auth_manager,
                                                                    query=query,
                                                                    session_id=session_id,
                                                                    api_method=post_api_method,
                                                                    endpoint_name=self.QUERIES_ENDPOINT,
                                                                    environment=self._environment,
                                                                    pinecone_client=self._pinecone_client,
                                                                    openai_client=self._openai_client,
                                                                    supabase_client=supabase_client):
                yield part

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=query.therapist_id,
                                    patient_id=query.patient_id,
                                    endpoint_name=self.QUERIES_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)
        except Exception as e:
            yield ("\n" + default_error_string)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
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
                                       background_tasks: BackgroundTasks,
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
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        logs_description = ''.join(['tz_identifier:', client_tz_identifier])
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               endpoint_name=self.GREETINGS_ENDPOINT,
                               description=logs_description)

        try:
            assert general_utilities.is_valid_timezone_identifier(client_tz_identifier), "Invalid timezone identifier parameter"

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            result = await self._assistant_manager.fetch_todays_greeting(client_tz_identifier=client_tz_identifier,
                                                                         therapist_id=therapist_id,
                                                                         session_id=session_id,
                                                                         endpoint_name=self.GREETINGS_ENDPOINT,
                                                                         api_method=get_api_method,
                                                                         environment=self._environment,
                                                                         auth_manager=self._auth_manager,
                                                                         openai_client=self._openai_client,
                                                                         supabase_client=supabase_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.GREETINGS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    http_status_code=status.HTTP_200_OK,
                                    description=logs_description,
                                    method=get_api_method)

            return {"message": result}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
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
                                              background_tasks: BackgroundTasks,
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
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.PRESESSION_TRAY_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Missing therapist_id param"
            assert len(patient_id or '') > 0, "Missing patient_id param"

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            json_response = await self._assistant_manager.create_patient_summary(patient_id=patient_id,
                                                                                 therapist_id=therapist_id,
                                                                                 environment=self._environment,
                                                                                 session_id=session_id,
                                                                                 endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                                                                 api_method=get_api_method,
                                                                                 auth_manager=self._auth_manager,
                                                                                 pinecone_client=self._pinecone_client,
                                                                                 openai_client=self._openai_client,
                                                                                 supabase_client=supabase_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)
            return json_response
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
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
                                                   background_tasks: BackgroundTasks,
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
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            json_questions = await self._assistant_manager.fetch_question_suggestions(therapist_id=therapist_id,
                                                                                      patient_id=patient_id,
                                                                                      auth_manager=self._auth_manager,
                                                                                      environment=self._environment,
                                                                                      session_id=session_id,
                                                                                      endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                                                                      api_method=get_api_method,
                                                                                      openai_client=self._openai_client,
                                                                                      pinecone_client=self._pinecone_client,
                                                                                      supabase_client=supabase_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)

            return json_questions
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
    body – the body associated with the request.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _add_patient_internal(self,
                                    response: Response,
                                    request: Request,
                                    background_tasks: BackgroundTasks,
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
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=post_api_method,
                               endpoint_name=self.PATIENTS_ENDPOINT,
                               therapist_id=therapist_id)

        try:
            body = body.dict(exclude_unset=True)

            assert 'consentment_channel' not in body or body['consentment_channel'] != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            patient_id = await self._assistant_manager.add_patient(auth_manager=self._auth_manager,
                                                                   filtered_body=body,
                                                                   therapist_id=therapist_id,
                                                                   session_id=session_id,
                                                                   openai_client=self._openai_client,
                                                                   supabase_client=supabase_client,
                                                                   pinecone_client=self._pinecone_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    method=post_api_method,
                                    endpoint_name=self.PATIENTS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK)

            return {"patient_id": patient_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.PATIENTS_ENDPOINT,
                             error_code=status_code,
                             therapist_id=therapist_id,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
    body – the body associated with the request.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_patient_internal(self,
                                       response: Response,
                                       request: Request,
                                       background_tasks: BackgroundTasks,
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
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response,
                                                     request=request,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        put_api_method = logger.API_METHOD_PUT
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=put_api_method,
                               endpoint_name=self.PATIENTS_ENDPOINT,
                               therapist_id=therapist_id,
                               patient_id=body.id)

        try:
            body = body.dict(exclude_unset=True)

            assert len(body['id'] or '') > 0, "Missing patient id param in payload"
            assert 'consentment_channel' not in body or body['consentment_channel'] != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            await self._assistant_manager.update_patient(auth_manager=self._auth_manager,
                                                         filtered_body=body,
                                                         session_id=session_id,
                                                         openai_client=self._openai_client,
                                                         supabase_client=supabase_client,
                                                         pinecone_client=self._pinecone_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    method=put_api_method,
                                    endpoint_name=self.PATIENTS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=body['id'],
                                    http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.PATIENTS_ENDPOINT,
                             error_code=status_code,
                             patient_id=body['id'],
                             description=description,
                             method=put_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
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
                                       background_tasks: BackgroundTasks,
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
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        delete_api_method = logger.API_METHOD_DELETE
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=delete_api_method,
                               endpoint_name=self.PATIENTS_ENDPOINT,
                               therapist_id=therapist_id,
                               patient_id=patient_id,)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)

            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            # Cascading will take care of deleting the session notes in Supabase.
            delete_result = supabase_client.delete(table_name="patients",
                                                   filters={
                                                       'id': patient_id
                                                   })
            assert len(delete_result.dict()['data']) > 0, "No patient found with the incoming patient_id"

            self._assistant_manager.delete_all_data_for_patient(therapist_id=therapist_id,
                                                                patient_id=patient_id,
                                                                pinecone_client=self._pinecone_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    method=delete_api_method,
                                    endpoint_name=self.PATIENTS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
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
                                              background_tasks: BackgroundTasks,
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
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.TOPICS_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            json_topics = await self._assistant_manager.fetch_frequent_topics(therapist_id=therapist_id,
                                                                              patient_id=patient_id,
                                                                              auth_manager=self._auth_manager,
                                                                              environment=self._environment,
                                                                              session_id=session_id,
                                                                              endpoint_name=self.TOPICS_ENDPOINT,
                                                                              api_method=get_api_method,
                                                                              openai_client=self._openai_client,
                                                                              pinecone_client=self._pinecone_client,
                                                                              supabase_client=supabase_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.TOPICS_ENDPOINT,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)

            return json_topics
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
    session_notes_text – the session notes to be adapted into SOAP.
    template – the template to be applied.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _transform_session_with_template_internal(self,
                                                        response: Response,
                                                        request: Request,
                                                        background_tasks: BackgroundTasks,
                                                        session_notes_text: str,
                                                        template: SessionNotesTemplate,
                                                        datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                        authorization: Annotated[Union[str, None], Cookie()],
                                                        session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=post_api_method,
                               endpoint_name=self.TEMPLATES_ENDPOINT,
                               therapist_id=therapist_id,)

        try:
            assert len(session_notes_text or '') > 0, "Empty session_notes_text param"
            assert len(therapist_id or '') > 0, "Empty therapist_id param"
            assert template != SessionNotesTemplate.FREE_FORM, "free_form is not a template that can be applied"

            soap_notes = await self._assistant_manager.adapt_session_notes_to_soap(auth_manager=self._auth_manager,
                                                                                   openai_client=self._openai_client,
                                                                                   therapist_id=therapist_id,
                                                                                   session_id=session_id,
                                                                                   session_notes_text=session_notes_text)
            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.TEMPLATES_ENDPOINT,
                                    therapist_id=therapist_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"soap_notes": soap_notes}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.TEMPLATES_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    # Private

    def _default_streaming_error_message_id(self, language_code: str):
        if language_code.startswith('es-'):
            # Spanish
            return 'streaming_qa_error_default_response_es'
        elif language_code.startswith('en-'):
            # English
            return 'streaming_qa_error_default_response_en'
        else:
            raise Exception("Unsupported language code")
