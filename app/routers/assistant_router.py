from fastapi import (APIRouter,
                     BackgroundTasks,
                     Body,
                     Cookie,
                     Header,
                     HTTPException,
                     Request,
                     Response,
                     status)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Annotated, AsyncIterable, Union

from ..dependencies.dependency_container import dependency_container
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.templates import SessionNotesTemplate
from ..internal import security
from ..internal.schemas import Gender, ENCRYPTED_PATIENTS_TABLE_NAME
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
from ..managers.email_manager import EmailManager

class TemplatePayload(BaseModel):
    session_notes_text: str
    template: SessionNotesTemplate = SessionNotesTemplate.SOAP

class AssistantRouter:

    SESSIONS_ENDPOINT = "/v1/sessions"
    QUERIES_ENDPOINT = "/v1/queries"
    PATIENTS_ENDPOINT = "/v1/patients"
    TEMPLATES_ENDPOINT = "/v1/templates"
    ROUTER_TAG = "assistant"

    def __init__(self, environment: str):
        self._environment = environment
        self._auth_manager = AuthManager()
        self._assistant_manager = AssistantManager()
        self._email_manager = EmailManager()
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def insert_new_session(insert_payload: SessionNotesInsert,
                                     request: Request,
                                     response: Response,
                                     background_tasks: BackgroundTasks,
                                     store_access_token: Annotated[str | None, Header()] = None,
                                     store_refresh_token: Annotated[str | None, Header()] = None,
                                     client_timezone_identifier: Annotated[str, Body()] = None,
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._insert_new_session_internal(body=insert_payload,
                                                           client_timezone_identifier=client_timezone_identifier,
                                                           background_tasks=background_tasks,
                                                           request=request,
                                                           response=response,
                                                           store_access_token=store_access_token,
                                                           store_refresh_token=store_refresh_token,
                                                           authorization=authorization,
                                                           session_id=session_id)

        @self.router.put(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_session(update_payload: SessionNotesUpdate,
                                 request: Request,
                                 response: Response,
                                 background_tasks: BackgroundTasks,
                                 client_timezone_identifier: Annotated[str, Body()] = None,
                                 store_access_token: Annotated[str | None, Header()] = None,
                                 store_refresh_token: Annotated[str | None, Header()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_session_internal(body=update_payload,
                                                       client_timezone_identifier=client_timezone_identifier,
                                                       response=response,
                                                       request=request,
                                                       background_tasks=background_tasks,
                                                       store_access_token=store_access_token,
                                                       store_refresh_token=store_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.delete(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_session(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 session_report_id: str = None,
                                 store_access_token: Annotated[str | None, Header()] = None,
                                 store_refresh_token: Annotated[str | None, Header()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_session_internal(session_report_id=session_report_id,
                                                       background_tasks=background_tasks,
                                                       request=request,
                                                       response=response,
                                                       store_access_token=store_access_token,
                                                       store_refresh_token=store_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.post(self.QUERIES_ENDPOINT, tags=[self.ROUTER_TAG])
        async def execute_assistant_query(query: AssistantQuery,
                                          request: Request,
                                          store_access_token: Annotated[str | None, Header()] = None,
                                          store_refresh_token: Annotated[str | None, Header()] = None,
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            request.state.session_id = session_id
            request.state.patient_id = query.patient_id
            if not self._auth_manager.access_token_is_valid(authorization):
                raise security.AUTH_TOKEN_EXPIRED_ERROR

            if store_access_token is None or store_refresh_token is None:
                raise security.STORE_TOKENS_ERROR

            try:
                supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                             refresh_token=store_refresh_token)
                therapist_id = supabase_client.get_current_user_id()
                request.state.therapist_id = therapist_id
            except Exception as e:
                status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
                dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                      method=request.method,
                                                                      patient_id=query.patient_id,
                                                                      error_code=status_code,
                                                                      description=str(e),
                                                                      session_id=session_id)
                raise security.STORE_TOKENS_ERROR

            try:
                assert len(query.patient_id or '') > 0, "Invalid patient_id in payload"
                assert len(query.text or '') > 0, "Invalid text in payload"

                return StreamingResponse(self._execute_assistant_query_internal(query=query,
                                                                                request=request,
                                                                                therapist_id=therapist_id,
                                                                                supabase_client=supabase_client,
                                                                                session_id=session_id),
                                         media_type="text/event-stream")
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        @self.router.get(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def get_patient(response: Response,
                              request: Request,
                              patient_id: str = None,
                              store_access_token: Annotated[str | None, Header()] = None,
                              store_refresh_token: Annotated[str | None, Header()] = None,
                              authorization: Annotated[Union[str, None], Cookie()] = None,
                              session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_patient_internal(response=response,
                                                    request=request,
                                                    patient_id=patient_id,
                                                    store_access_token=store_access_token,
                                                    store_refresh_token=store_refresh_token,
                                                    authorization=authorization,
                                                    session_id=session_id)

        @self.router.post(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def add_patient(response: Response,
                              request: Request,
                              background_tasks: BackgroundTasks,
                              body: PatientInsertPayload,
                              store_access_token: Annotated[str | None, Header()] = None,
                              store_refresh_token: Annotated[str | None, Header()] = None,
                              authorization: Annotated[Union[str, None], Cookie()] = None,
                              session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_patient_internal(response=response,
                                                    request=request,
                                                    background_tasks=background_tasks,
                                                    body=body,
                                                    store_access_token=store_access_token,
                                                    store_refresh_token=store_refresh_token,
                                                    authorization=authorization,
                                                    session_id=session_id)

        @self.router.put(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_patient(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 body: PatientUpdatePayload,
                                 store_access_token: Annotated[str | None, Header()] = None,
                                 store_refresh_token: Annotated[str | None, Header()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_patient_internal(response=response,
                                                       request=request,
                                                       body=body,
                                                       background_tasks=background_tasks,
                                                       store_access_token=store_access_token,
                                                       store_refresh_token=store_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.delete(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_patient(request: Request,
                                 response: Response,
                                 patient_id: str = None,
                                 store_access_token: Annotated[str | None, Header()] = None,
                                 store_refresh_token: Annotated[str | None, Header()] = None,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_patient_internal(request=request,
                                                       response=response,
                                                       patient_id=patient_id,
                                                       store_access_token=store_access_token,
                                                       store_refresh_token=store_refresh_token,
                                                       authorization=authorization,
                                                       session_id=session_id)

        @self.router.post(self.TEMPLATES_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transform_session_with_template(request: Request,
                                                  response: Response,
                                                  background_tasks: BackgroundTasks,
                                                  body: TemplatePayload,
                                                  store_access_token: Annotated[str | None, Header()] = None,
                                                  store_refresh_token: Annotated[str | None, Header()] = None,
                                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transform_session_with_template_internal(request=request,
                                                                        response=response,
                                                                        background_tasks=background_tasks,
                                                                        session_notes_text=body.session_notes_text,
                                                                        template=body.template,
                                                                        store_access_token=store_access_token,
                                                                        store_refresh_token=store_refresh_token,
                                                                        authorization=authorization,
                                                                        session_id=session_id)

    """
    Stores a new session report.

    Arguments:
    body – the incoming request json body.
    client_timezone_identifier – the client's timezone identifier.
    request – the request object.
    response – the response model with which to create the final response.
    background_tasks – object for scheduling concurrent tasks.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _insert_new_session_internal(self,
                                           body: SessionNotesInsert,
                                           client_timezone_identifier: str,
                                           request: Request,
                                           response: Response,
                                           background_tasks: BackgroundTasks,
                                           store_access_token: Annotated[str | None, Header()],
                                           store_refresh_token: Annotated[str | None, Header()],
                                           authorization: Annotated[Union[str, None], Cookie()],
                                           session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        request.state.patient_id = body.patient_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                      method=request.method,
                                                                      patient_id=body.patient_id,
                                                                      error_code=status_code,
                                                                      description=str(e),
                                                                      session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.model_dump(exclude_unset=True)

            assert len(client_timezone_identifier or '') == 0 or general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"

            tz_exists = len(client_timezone_identifier or '') > 0
            date_is_valid = datetime_handler.is_valid_date(date_input=body['session_date'],
                                                           incoming_date_format=datetime_handler.DATE_FORMAT,
                                                           tz_identifier=client_timezone_identifier)
            assert 'session_date' not in body or (tz_exists and date_is_valid), "Invalid payload. Need a timezone identifier, and session_date (mm-dd-yyyy) should not be in the future."

            language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
            session_report_id = await self._assistant_manager.process_new_session_data(language_code=language_code,
                                                                                       environment=self._environment,
                                                                                       auth_manager=self._auth_manager,
                                                                                       patient_id=body['patient_id'],
                                                                                       notes_text=body['notes_text'],
                                                                                       session_date=body['session_date'],
                                                                                       source=SessionNotesSource.MANUAL_INPUT,
                                                                                       background_tasks=background_tasks,
                                                                                       session_id=session_id,
                                                                                       therapist_id=therapist_id,
                                                                                       supabase_client=supabase_client,
                                                                                       email_manager=self._email_manager)
            request.state.session_report_id = session_report_id
            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                      method=request.method,
                                                                      patient_id=body['patient_id'],
                                                                      error_code=status_code,
                                                                      description=description,
                                                                      session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates a session report.

    Arguments:
    body – the incoming request body.
    client_timezone_identifier – the client's timezone identifier.
    request – the request object.
    response – the response model with which to create the final response.
    background_tasks – object for scheduling concurrent tasks.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_session_internal(self,
                                       body: SessionNotesUpdate,
                                       client_timezone_identifier: str,
                                       request: Request,
                                       response: Response,
                                       background_tasks: BackgroundTasks,
                                       store_access_token: Annotated[str | None, Header()],
                                       store_refresh_token: Annotated[str | None, Header()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        request.state.session_report_id = body.id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                      method=request.method,
                                                                      session_report_id=body.id,
                                                                      error_code=status_code,
                                                                      description=str(e),
                                                                      session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.model_dump(exclude_unset=True)

            assert len(client_timezone_identifier or '') == 0 or general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"

            tz_exists = len(client_timezone_identifier or '') > 0
            date_is_valid = datetime_handler.is_valid_date(date_input=body['session_date'],
                                                           incoming_date_format=datetime_handler.DATE_FORMAT,
                                                           tz_identifier=client_timezone_identifier)
            assert 'session_date' not in body or (tz_exists and date_is_valid), "Invalid payload. Need a timezone identifier, and session_date (mm-dd-yyyy) should not be in the future."

            language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
            await self._assistant_manager.update_session(language_code=language_code,
                                                         environment=self._environment,
                                                         background_tasks=background_tasks,
                                                         auth_manager=self._auth_manager,
                                                         filtered_body=body,
                                                         session_id=session_id,
                                                         supabase_client=supabase_client,
                                                         email_manager=self._email_manager)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                      method=request.method,
                                                                      session_report_id=body['id'],
                                                                      error_code=status_code,
                                                                      description=description,
                                                                      session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes a session report.

    Arguments:
    session_report_id – the id for the incoming session report.
    request – the request object.
    response – the response model with which to create the final response.
    background_tasks – object for scheduling concurrent tasks.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_session_internal(self,
                                       session_report_id: str,
                                       request: Request,
                                       response: Response,
                                       background_tasks: BackgroundTasks,
                                       store_access_token: Annotated[str | None, Header()],
                                       store_refresh_token: Annotated[str | None, Header()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        request.state.session_report_id = session_report_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                      method=request.method,
                                                                      session_report_id=session_report_id,
                                                                      error_code=status_code,
                                                                      description=str(e),
                                                                      session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            assert len(session_report_id or '') > 0, "Received invalid session_report_id"
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                      method=request.method,
                                                                      therapist_id=therapist_id,
                                                                      session_report_id=session_report_id,
                                                                      error_code=status_code,
                                                                      description=description,
                                                                      session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

        try:
            language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
            await self._assistant_manager.delete_session(language_code=language_code,
                                                         email_manager=self._email_manager,
                                                         environment=self._environment,
                                                         session_id=session_id,
                                                         background_tasks=background_tasks,
                                                         therapist_id=therapist_id,
                                                         session_report_id=session_report_id,
                                                         supabase_client=supabase_client)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description,
                                                                  session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Executes a query to our assistant system.
    Returns the query response.

    Arguments:
    request – the request object.
    query – the query that will be executed.
    therapist_id – the therapist id associated with the query.
    supabase_client – the supabase client to be used internally.
    session_id – the session_id cookie, if exists.
    """
    async def _execute_assistant_query_internal(self,
                                                request: Request,
                                                query: AssistantQuery,
                                                therapist_id: str,
                                                supabase_client: SupabaseBaseClass,
                                                session_id: Annotated[Union[str, None], Cookie()]) -> AsyncIterable[str]:
        try:
            async for part in self._assistant_manager.query_session(query=query,
                                                                    session_id=session_id,
                                                                    therapist_id=therapist_id,
                                                                    environment=self._environment,
                                                                    supabase_client=supabase_client):
                yield part
        except Exception as e:
            yield ("\n" + self._assistant_manager.default_streaming_error_message(user_id=therapist_id,
                                                                                  supabase_client=supabase_client))
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  patient_id=query.patient_id,
                                                                  error_code=general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST),
                                                                  description=str(e),
                                                                  session_id=session_id)

    async def _get_patient_internal(self,
                                    request: Request,
                                    response: Response,
                                    patient_id: str,
                                    store_access_token: Annotated[str | None, Header()],
                                    store_refresh_token: Annotated[str | None, Header()],
                                    authorization: Annotated[Union[str, None], Cookie()],
                                    session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            assert len(patient_id or '') > 0, "Invalid patient_id in payload"

            patient_data = await self._assistant_manager.retrieve_patient(supabase_client=supabase_client,
                                                                          patient_id=patient_id)
            request.state.patient_id = patient_id
            return {"patient_data": patient_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  therapist_id=therapist_id,
                                                                  error_code=status_code,
                                                                  description=description,
                                                                  session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Adds a patient.

    Arguments:
    request – the request object.
    response – the object to be used for constructing the final response.
    background_tasks – object for scheduling concurrent tasks.
    body – the body associated with the request.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _add_patient_internal(self,
                                    request: Request,
                                    response: Response,
                                    background_tasks: BackgroundTasks,
                                    body: PatientInsertPayload,
                                    store_access_token: Annotated[str | None, Header()],
                                    store_refresh_token: Annotated[str | None, Header()],
                                    authorization: Annotated[Union[str, None], Cookie()],
                                    session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.model_dump(exclude_unset=True)

            assert 'consentment_channel' not in body or body['consentment_channel'] != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
            patient_id = await self._assistant_manager.add_patient(language_code=language_code,
                                                                   background_tasks=background_tasks,
                                                                   filtered_body=body,
                                                                   therapist_id=therapist_id,
                                                                   session_id=session_id,
                                                                   supabase_client=supabase_client,
                                                                   email_manager=self._email_manager)
            request.state.patient_id = patient_id
            return {"patient_id": patient_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  therapist_id=therapist_id,
                                                                  error_code=status_code,
                                                                  description=description,
                                                                  session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates a patient.

    Arguments:
    request – the request object.
    response – the object to be used for constructing the final response.
    background_tasks – object for scheduling concurrent tasks.
    body – the body associated with the request.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_patient_internal(self,
                                       request: Request,
                                       response: Response,
                                       background_tasks: BackgroundTasks,
                                       body: PatientUpdatePayload,
                                       store_access_token: Annotated[str | None, Header()],
                                       store_refresh_token: Annotated[str | None, Header()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        request.state.patient_id = body.id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  patient_id=body.id,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.model_dump(exclude_unset=True)

            assert len(body['id'] or '') > 0, "Missing patient id param in payload"
            assert 'consentment_channel' not in body or body['consentment_channel'] != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            await self._assistant_manager.update_patient(filtered_body=body,
                                                         session_id=session_id,
                                                         background_tasks=background_tasks,
                                                         supabase_client=supabase_client)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  patient_id=body['id'],
                                                                  error_code=status_code,
                                                                  description=description,
                                                                  session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes a patient.

    Arguments:
    request – the request object.
    response – the object to be used for constructing the final response.
    patient_id – the id for the patient to be deleted.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_patient_internal(self,
                                       request: Request,
                                       response: Response,
                                       patient_id: str,
                                       store_access_token: Annotated[str | None, Header()],
                                       store_refresh_token: Annotated[str | None, Header()],
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        request.state.patient_id = patient_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  patient_id=patient_id,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            assert len(patient_id or '') > 0, "Missing patient_id param"
            assert len(therapist_id or '') > 0, "Missing therapist_id param"

            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name=ENCRYPTED_PATIENTS_TABLE_NAME)
            assert (0 != len(patient_query['data'])), "There isn't a patient-therapist match with the incoming ids."

            # Cascading will take care of deleting the session notes in Supabase.
            delete_result = supabase_client.delete(table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                                                   filters={
                                                       'id': patient_id
                                                   })
            assert len(delete_result['data']) > 0, "No patient found with the incoming patient_id"

            self._assistant_manager.delete_all_data_for_patient(therapist_id=therapist_id,
                                                                patient_id=patient_id)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  therapist_id=therapist_id,
                                                                  error_code=status_code,
                                                                  description=description,
                                                                  session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Adapts an incoming set of session notes into the SOAP format and returns the result.

    Arguments:
    request – the request object.
    response – the response model used for the final response that will be returned.
    background_tasks – object for scheduling concurrent tasks.
    session_notes_text – the session notes to be adapted into SOAP.
    template – the template to be applied.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _transform_session_with_template_internal(self,
                                                        request: Request,
                                                        response: Response,
                                                        background_tasks: BackgroundTasks,
                                                        session_notes_text: str,
                                                        template: SessionNotesTemplate,
                                                        store_access_token: Annotated[str | None, Header()],
                                                        store_refresh_token: Annotated[str | None, Header()],
                                                        authorization: Annotated[Union[str, None], Cookie()],
                                                        session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        request.state.notes_template = template.value
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise security.STORE_TOKENS_ERROR

        try:
            assert len(session_notes_text or '') > 0, "Empty session_notes_text param"
            assert len(therapist_id or '') > 0, "Empty therapist_id param"
            assert template != SessionNotesTemplate.FREE_FORM, "free_form is not a template that can be applied"

            soap_notes = await self._assistant_manager.adapt_session_notes_to_soap(therapist_id=therapist_id,
                                                                                   session_id=session_id,
                                                                                   session_notes_text=session_notes_text)
            return {"soap_notes": soap_notes}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description,
                                                                  session_id=session_id)
            raise HTTPException(status_code=status_code,
                                detail=description)
