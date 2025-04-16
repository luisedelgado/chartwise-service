from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Cookie,
    Security,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Annotated, AsyncIterable, Optional, Union

from ..dependencies.dependency_container import AwsDbBaseClass, dependency_container
from ..dependencies.api.templates import SessionNotesTemplate
from ..internal.security.cognito_auth import verify_cognito_token
from ..internal.security.security_schema import SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR
from ..internal.schemas import (
    Gender,
    ENCRYPTED_PATIENTS_TABLE_NAME,
    TimeRange,
    USER_ID_KEY
)
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import (
    AssistantManager,
    AssistantQuery,
    PatientConsentmentChannel,
    PatientInsertPayload,
    PatientUpdatePayload,
    SessionNotesInsert,
    SessionNotesSource,
    SessionNotesUpdate
)
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager

class TemplatePayload(BaseModel):
    session_notes_text: str
    template: SessionNotesTemplate = SessionNotesTemplate.SOAP

class AssistantRouter:

    SESSIONS_ENDPOINT = "/v1/sessions"
    SINGLE_SESSION_ENDPOINT = "/v1/sessions/{session_report_id}"
    QUERIES_ENDPOINT = "/v1/queries"
    PATIENTS_ENDPOINT = "/v1/patients"
    SINGLE_PATIENT_ENDPOINT = "/v1/patients/{patient_id}"
    TEMPLATES_ENDPOINT = "/v1/templates"
    ATTENDANCE_INSIGHTS_ENDPOINT = "/v1/attendance-insights"
    BRIEFINGS_ENDPOINT = "/v1/briefings"
    QUESTION_SUGGESTIONS_ENDPOINT = "/v1/question-suggestions"
    RECENT_TOPICS_ENDPOINT = "/v1/recent-topics"
    ASSISTANT_ROUTER_TAG = "assistant"
    PATIENTS_ROUTER_TAG = "patients"

    def __init__(self, environment: str):
        self._environment = environment
        self._auth_manager = AuthManager()
        self._assistant_manager = AssistantManager()
        self._email_manager = EmailManager()
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self):
        """
        Registers the set of routes that the class' router can access.
        """
        @self.router.get(self.SINGLE_SESSION_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def retrieve_single_session_report(response: Response,
                                                 request: Request,
                                                 _: dict = Security(verify_cognito_token),
                                                 session_report_id: str = Path(..., min_length=1),
                                                 session_token: Annotated[Union[str, None], Cookie()] = None,
                                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._retrieve_single_session_report_internal(
                response=response,
                request=request,
                session_report_id=session_report_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.get(self.SESSIONS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def get_session_reports(response: Response,
                                      request: Request,
                                      year: str = Query(None),
                                      most_recent_n: int = Query(None),
                                      time_range: Optional[TimeRange] = Query(None),
                                      patient_id: str = None,
                                      _: dict = Security(verify_cognito_token),
                                      session_token: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_session_reports_internal(
                response=response,
                request=request,
                year=year,
                most_recent_n=most_recent_n,
                time_range=time_range,
                patient_id=patient_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.post(self.SESSIONS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def insert_new_session(insert_payload: SessionNotesInsert,
                                     request: Request,
                                     response: Response,
                                     background_tasks: BackgroundTasks,
                                     _: dict = Security(verify_cognito_token),
                                     client_timezone_identifier: Annotated[str, Body()] = None,
                                     session_token: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._insert_new_session_internal(
                body=insert_payload,
                client_timezone_identifier=client_timezone_identifier,
                background_tasks=background_tasks,
                request=request,
                response=response,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.put(self.SESSIONS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def update_session(update_payload: SessionNotesUpdate,
                                 request: Request,
                                 response: Response,
                                 background_tasks: BackgroundTasks,
                                 _: dict = Security(verify_cognito_token),
                                 client_timezone_identifier: Annotated[str, Body()] = None,
                                 session_token: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_session_internal(
                body=update_payload,
                client_timezone_identifier=client_timezone_identifier,
                response=response,
                request=request,
                background_tasks=background_tasks,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.delete(self.SESSIONS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def delete_session(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 session_report_id: str = None,
                                 _: dict = Security(verify_cognito_token),
                                 session_token: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_session_internal(
                session_report_id=session_report_id,
                background_tasks=background_tasks,
                request=request,
                response=response,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.post(self.QUERIES_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def execute_assistant_query(query: AssistantQuery,
                                          request: Request,
                                          response: Response,
                                          _: dict = Security(verify_cognito_token),
                                          session_token: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            request.state.session_id = session_id
            request.state.patient_id = query.patient_id
            if not self._auth_manager.session_token_is_valid(session_token):
                raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

            try:
                user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
                request.state.therapist_id = user_id
                await self._auth_manager.refresh_session(
                    user_id=user_id,
                    response=response
                )
            except Exception as e:
                status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
                dependency_container.inject_influx_client().log_error(
                    endpoint_name=request.url.path,
                    method=request.method,
                    patient_id=query.patient_id,
                    error_code=status_code,
                    description=str(e),
                    session_id=session_id
                )
                raise Exception(e)

            try:
                assert general_utilities.is_valid_uuid(query.patient_id or '') > 0, "Invalid patient_id in payload"
                assert len(query.text or '') > 0, "Invalid text in payload"

                aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
                return StreamingResponse(self._execute_assistant_query_internal(
                    query=query,
                    request=request,
                    therapist_id=user_id,
                    aws_db_client=aws_db_client,
                    session_id=session_id
                ), media_type="text/event-stream")
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        @self.router.get(self.SINGLE_PATIENT_ENDPOINT, tags=[self.PATIENTS_ROUTER_TAG])
        async def get_single_patient(response: Response,
                                     request: Request,
                                     patient_id: str = Path(..., min_length=1),
                                     _: dict = Security(verify_cognito_token),
                                     session_token: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_single_patient_internal(
                response=response,
                request=request,
                patient_id=patient_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.get(self.PATIENTS_ENDPOINT, tags=[self.PATIENTS_ROUTER_TAG])
        async def get_patients(response: Response,
                               request: Request,
                               _: dict = Security(verify_cognito_token),
                               session_token: Annotated[Union[str, None], Cookie()] = None,
                               session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_patients_internal(
                response=response,
                request=request,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.post(self.PATIENTS_ENDPOINT, tags=[self.PATIENTS_ROUTER_TAG])
        async def add_patient(response: Response,
                              request: Request,
                              background_tasks: BackgroundTasks,
                              body: PatientInsertPayload,
                              _: dict = Security(verify_cognito_token),
                              session_token: Annotated[Union[str, None], Cookie()] = None,
                              session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_patient_internal(
                response=response,
                request=request,
                background_tasks=background_tasks,
                body=body,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.put(self.PATIENTS_ENDPOINT, tags=[self.PATIENTS_ROUTER_TAG])
        async def update_patient(response: Response,
                                 request: Request,
                                 background_tasks: BackgroundTasks,
                                 body: PatientUpdatePayload,
                                 _: dict = Security(verify_cognito_token),
                                 session_token: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_patient_internal(
                response=response,
                request=request,
                body=body,
                background_tasks=background_tasks,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.delete(self.PATIENTS_ENDPOINT, tags=[self.PATIENTS_ROUTER_TAG])
        async def delete_patient(request: Request,
                                 response: Response,
                                 patient_id: str = None,
                                 _: dict = Security(verify_cognito_token),
                                 session_token: Annotated[Union[str, None], Cookie()] = None,
                                 session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_patient_internal(
                request=request,
                response=response,
                patient_id=patient_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.get(self.ATTENDANCE_INSIGHTS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def get_attendance_insights(response: Response,
                                          request: Request,
                                          patient_id: str = None,
                                          _: dict = Security(verify_cognito_token),
                                          session_token: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_attendance_insights_internal(
                response=response,
                request=request,
                patient_id=patient_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.get(self.BRIEFINGS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def get_briefing(response: Response,
                               request: Request,
                               patient_id: str = None,
                               _: dict = Security(verify_cognito_token),
                               session_token: Annotated[Union[str, None], Cookie()] = None,
                               session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_briefing_internal(
                response=response,
                request=request,
                patient_id=patient_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.get(self.QUESTION_SUGGESTIONS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def get_question_suggestions(response: Response,
                                           request: Request,
                                           patient_id: str = None,
                                           _: dict = Security(verify_cognito_token),
                                           session_token: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_question_suggestions_internal(
                response=response,
                request=request,
                patient_id=patient_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.get(self.RECENT_TOPICS_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def get_recent_topics(response: Response,
                                    request: Request,
                                    patient_id: str = None,
                                    _: dict = Security(verify_cognito_token),
                                    session_token: Annotated[Union[str, None], Cookie()] = None,
                                    session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._get_recent_topics_internal(
                response=response,
                request=request,
                patient_id=patient_id,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.post(self.TEMPLATES_ENDPOINT, tags=[self.ASSISTANT_ROUTER_TAG])
        async def transform_session_with_template(request: Request,
                                                  response: Response,
                                                  body: TemplatePayload,
                                                  _: dict = Security(verify_cognito_token),
                                                  session_token: Annotated[Union[str, None], Cookie()] = None,
                                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transform_session_with_template_internal(
                request=request,
                response=response,
                session_notes_text=body.session_notes_text,
                template=body.template,
                session_token=session_token,
                session_id=session_id
            )

    async def _retrieve_single_session_report_internal(self,
                                                       request: Request,
                                                       response: Response,
                                                       session_report_id: str,
                                                       session_token: Annotated[Union[str, None], Cookie()],
                                                       session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a session report.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        session_report_id – the ID of the session report to be retrieved.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            if not session_report_id.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parameter session_report_id cannot be empty."
                )

            session_report_data = await self._assistant_manager.retrieve_single_session_report(
                therapist_id=user_id,
                session_report_id=session_report_id,
                request=request,
            )
            request.state.patient_id = None if len(session_report_data or '') == 0 else session_report_data['patient_id']
            return {"session_report_data": session_report_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _get_session_reports_internal(self,
                                            request: Request,
                                            response: Response,
                                            year: str,
                                            most_recent_n: int,
                                            time_range: str,
                                            patient_id: str,
                                            session_token: Annotated[Union[str, None], Cookie()],
                                            session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a batch of session reports.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        year – the year associated with the batch of sessions that will be returned.
        most_recent_n – the count of (most recent) sessions to be retrieved.
        time_range – the time range for which a batch of sessions will be retrieved.
        patient_id – the patient id associated with the batch of sessions that will be returned.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = patient_id

        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            filters = [year, most_recent_n, time_range]
            set_filters = sum(filter is not None for filter in filters)

            assert set_filters == 1, "Only one of 'year', 'recent', or 'range' needs to be specified."
            assert year is None or datetime_handler.validate_year(year=year), "Invalid year parameteter"
            assert general_utilities.is_valid_uuid(patient_id), "Invalid patient_id parameteter"

            session_reports_data = await self._assistant_manager.retrieve_session_reports(
                therapist_id=user_id,
                patient_id=patient_id,
                year=year,
                time_range=time_range,
                most_recent=most_recent_n,
                request=request,
            )
            return {"session_reports_data": session_reports_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _insert_new_session_internal(self,
                                           body: SessionNotesInsert,
                                           client_timezone_identifier: str,
                                           request: Request,
                                           response: Response,
                                           background_tasks: BackgroundTasks,
                                           session_token: Annotated[Union[str, None], Cookie()],
                                           session_id: Annotated[Union[str, None], Cookie()]):
        """
        Stores a new session report.

        Arguments:
        body – the incoming request json body.
        client_timezone_identifier – the client's timezone identifier.
        request – the request object.
        response – the response model with which to create the final response.
        background_tasks – object for scheduling concurrent tasks.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = body.patient_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                patient_id=body.patient_id,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            body = body.model_dump(exclude_unset=True)
            patient_id = body['patient_id']

            assert general_utilities.is_valid_uuid(patient_id), "Invalid patient_id body param"
            assert len(client_timezone_identifier or '') == 0 or general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"

            tz_exists = len(client_timezone_identifier or '') > 0
            date_is_valid = datetime_handler.is_valid_date(
                date_input=body['session_date'],
                incoming_date_format=datetime_handler.DATE_FORMAT,
                tz_identifier=client_timezone_identifier
            )
            assert 'session_date' not in body or (tz_exists and date_is_valid), "Invalid payload. Need a timezone identifier, and session_date (mm-dd-yyyy) should not be in the future."

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client,
            )
            session_report_id = await self._assistant_manager.process_new_session_data(
                language_code=language_code,
                environment=self._environment,
                auth_manager=self._auth_manager,
                patient_id=patient_id,
                notes_text=body['notes_text'],
                session_date=body['session_date'],
                source=SessionNotesSource.MANUAL_INPUT,
                background_tasks=background_tasks,
                session_id=session_id,
                therapist_id=user_id,
                email_manager=self._email_manager,
                request=request,
            )
            request.state.session_report_id = session_report_id
            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                patient_id=body['patient_id'],
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _update_session_internal(self,
                                       body: SessionNotesUpdate,
                                       client_timezone_identifier: str,
                                       request: Request,
                                       response: Response,
                                       background_tasks: BackgroundTasks,
                                       session_token: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        """
        Updates a session report.

        Arguments:
        body – the incoming request body.
        client_timezone_identifier – the client's timezone identifier.
        request – the request object.
        response – the response model with which to create the final response.
        background_tasks – object for scheduling concurrent tasks.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.session_report_id = body.id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                session_report_id=body.id,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            body = body.model_dump(exclude_unset=True)

            assert general_utilities.is_valid_uuid(body['id']), "Invalid session report ID param in body"
            assert len(client_timezone_identifier or '') == 0 or general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"

            tz_exists = len(client_timezone_identifier or '') > 0
            date_is_valid = datetime_handler.is_valid_date(
                date_input=body['session_date'],
                incoming_date_format=datetime_handler.DATE_FORMAT,
                tz_identifier=client_timezone_identifier
            )
            assert 'session_date' not in body or (tz_exists and date_is_valid), "Invalid payload. Need a timezone identifier, and session_date (mm-dd-yyyy) should not be in the future."

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client,
            )
            patient_id = (await self._assistant_manager.update_session(
                therapist_id=user_id,
                language_code=language_code,
                environment=self._environment,
                background_tasks=background_tasks,
                auth_manager=self._auth_manager,
                filtered_body=body,
                session_id=session_id,
                aws_db_client=aws_db_client,
                email_manager=self._email_manager,
                request=request,)
            )['patient_id']
            request.state.patient_id = patient_id
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                session_report_id=body['id'],
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(status_code=status_code,
                                detail=description)

    async def _delete_session_internal(self,
                                       session_report_id: str,
                                       request: Request,
                                       response: Response,
                                       background_tasks: BackgroundTasks,
                                       session_token: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()],):
        """
        Deletes a session report.

        Arguments:
        session_report_id – the id for the incoming session report.
        request – the request object.
        response – the response model with which to create the final response.
        background_tasks – object for scheduling concurrent tasks.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.session_report_id = session_report_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                session_report_id=session_report_id,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            assert general_utilities.is_valid_uuid(session_report_id), "Received invalid session_report_id"
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                session_report_id=session_report_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(status_code=status_code,
                                detail=description)

        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client
            )
            patient_id = (await self._assistant_manager.delete_session(
                language_code=language_code,
                email_manager=self._email_manager,
                environment=self._environment,
                session_id=session_id,
                background_tasks=background_tasks,
                therapist_id=user_id,
                session_report_id=session_report_id,
                aws_db_client=aws_db_client,
                request=request,
            ))['patient_id']
            request.state.patient_id = patient_id
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _execute_assistant_query_internal(self,
                                                request: Request,
                                                query: AssistantQuery,
                                                therapist_id: str,
                                                aws_db_client: AwsDbBaseClass,
                                                session_id: Annotated[Union[str, None], Cookie()]) -> AsyncIterable[str]:
        """
        Executes a query to our assistant system.
        Returns the query response.

        Arguments:
        request – the request object.
        query – the query that will be executed.
        therapist_id – the therapist id associated with the query.
        aws_db_client – the AWS database client to interact with the database.
        session_id – the session_id cookie, if exists.
        """
        try:
            async for part in self._assistant_manager.query_session(
                query=query,
                session_id=session_id,
                therapist_id=therapist_id,
                environment=self._environment,
                request=request,
            ):
                yield part
        except Exception as e:
            yield ("\n" + (await self._assistant_manager.default_streaming_error_message(
                user_id=therapist_id,
            )))
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                patient_id=query.patient_id,
                error_code=general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST),
                description=str(e),
                session_id=session_id
            )

    async def _get_single_patient_internal(self,
                                           request: Request,
                                           response: Response,
                                           patient_id: str,
                                           session_token: Annotated[Union[str, None], Cookie()],
                                           session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a patient.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        patient_id – the id for the incoming patient.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = patient_id

        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            if not patient_id.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parameter patient_id cannot be empty."
                )

            patient_data = await self._assistant_manager.retrieve_single_patient(
                therapist_id=user_id,
                patient_id=patient_id,
                request=request,
            )
            return {"patient_data": patient_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _get_patients_internal(self,
                                     request: Request,
                                     response: Response,
                                     session_token: Annotated[Union[str, None], Cookie()],
                                     session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a batch of patients.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id

        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            patients_data = await self._assistant_manager.retrieve_patients(
                therapist_id=user_id,
                request=request,
            )
            return {"patients_data": patients_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _add_patient_internal(self,
                                    request: Request,
                                    response: Response,
                                    background_tasks: BackgroundTasks,
                                    body: PatientInsertPayload,
                                    session_token: Annotated[Union[str, None], Cookie()],
                                    session_id: Annotated[Union[str, None], Cookie()]):
        """
        Adds a patient.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        background_tasks – object for scheduling concurrent tasks.
        body – the body associated with the request.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            body = body.model_dump(exclude_unset=True)

            assert 'consentment_channel' not in body or body['consentment_channel'] != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(
                date_input=body['birth_date'],
                incoming_date_format=datetime_handler.DATE_FORMAT
            ), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client,
            )
            patient_id = await self._assistant_manager.add_patient(
                language_code=language_code,
                background_tasks=background_tasks,
                filtered_body=body,
                therapist_id=user_id,
                session_id=session_id,
                email_manager=self._email_manager,
                request=request,
            )
            request.state.patient_id = patient_id
            return {"patient_id": patient_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _update_patient_internal(self,
                                       request: Request,
                                       response: Response,
                                       background_tasks: BackgroundTasks,
                                       body: PatientUpdatePayload,
                                       session_token: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        """
        Updates a patient.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        background_tasks – object for scheduling concurrent tasks.
        body – the body associated with the request.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = body.id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                patient_id=body.id,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            body = body.model_dump(exclude_unset=True)

            assert general_utilities.is_valid_uuid(body['id'] or '') > 0, "Missing patient id param in payload"
            assert 'consentment_channel' not in body or body['consentment_channel'] != PatientConsentmentChannel.UNDEFINED, '''Invalid parameter 'undefined' for consentment_channel.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(
                date_input=body['birth_date'],
                incoming_date_format=datetime_handler.DATE_FORMAT
            ), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            await self._assistant_manager.update_patient(
                therapist_id=user_id,
                filtered_body=body,
                session_id=session_id,
                background_tasks=background_tasks,
                request=request,
            )
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                patient_id=body['id'],
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(status_code=status_code,
                                detail=description)

    async def _delete_patient_internal(self,
                                       request: Request,
                                       response: Response,
                                       patient_id: str,
                                       session_token: Annotated[Union[str, None], Cookie()],
                                       session_id: Annotated[Union[str, None], Cookie()]):
        """
        Deletes a patient.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        patient_id – the id for the patient to be deleted.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = patient_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                patient_id=patient_id,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id param"
            assert len(user_id or '') > 0, "Missing therapist_id param"

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            patient_query = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields="*",
                filters={
                    'therapist_id': user_id,
                    'id': patient_id
                },
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME
            )
            assert (0 != len(patient_query)), "There isn't a patient-therapist match with the incoming ids."

            # Cascading will take care of deleting the session notes as well.
            delete_result = await aws_db_client.delete(
                user_id=user_id,
                request=request,
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                filters={
                    'id': patient_id
                }
            )
            assert len(delete_result) > 0, "No patient found with the incoming patient_id"

            self._assistant_manager.delete_all_data_for_patient(
                therapist_id=user_id,
                patient_id=patient_id
            )
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _get_attendance_insights_internal(self,
                                                request: Request,
                                                response: Response,
                                                patient_id: str,
                                                session_token: Annotated[Union[str, None], Cookie()],
                                                session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a patient's attendance insights.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        patient_id – the id for the incoming patient.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id in payload"

            attendance_insights_data = await self._assistant_manager.retrieve_patient_insights(
                therapist_id=user_id,
                patient_id=patient_id,
                request=request,
            )
            request.state.patient_id = patient_id
            return {"attendance_insights_data": attendance_insights_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _get_briefing_internal(self,
                                     request: Request,
                                     response: Response,
                                     patient_id: str,
                                     session_token: Annotated[Union[str, None], Cookie()],
                                     session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a patient's latest briefing.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        patient_id – the id for the incoming patient.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id in payload"

            briefing_data = await self._assistant_manager.retrieve_briefing(
                therapist_id=user_id,
                patient_id=patient_id,
                request=request,
            )
            request.state.patient_id = patient_id
            return {"briefing_data": briefing_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _get_question_suggestions_internal(self,
                                                 request: Request,
                                                 response: Response,
                                                 patient_id: str,
                                                 session_token: Annotated[Union[str, None], Cookie()],
                                                 session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a patient's latest question suggestions.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        patient_id – the id for the incoming patient.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id in payload"

            question_suggestions_data = await self._assistant_manager.retrieve_question_suggestions(
                therapist_id=user_id,
                patient_id=patient_id,
                request=request,
            )
            request.state.patient_id = patient_id
            return {"question_suggestions_data": question_suggestions_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _get_recent_topics_internal(self,
                                          request: Request,
                                          response: Response,
                                          patient_id: str,
                                          session_token: Annotated[Union[str, None], Cookie()],
                                          session_id: Annotated[Union[str, None], Cookie()]):
        """
        Retrieves a patient's latest recent topics.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        patient_id – the id for the incoming patient.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id in payload"

            recent_topics_data = await self._assistant_manager.recent_topics_data(
                therapist_id=user_id,
                patient_id=patient_id,
                request=request,
            )
            request.state.patient_id = patient_id
            return {"recent_topics_data": recent_topics_data}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                therapist_id=user_id,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _transform_session_with_template_internal(self,
                                                        request: Request,
                                                        response: Response,
                                                        session_notes_text: str,
                                                        template: SessionNotesTemplate,
                                                        session_token: Annotated[Union[str, None], Cookie()],
                                                        session_id: Annotated[Union[str, None], Cookie()]):
        """
        Adapts an incoming set of session notes into the SOAP format and returns the result.

        Arguments:
        request – the request object.
        response – the response model used for the final response that will be returned.
        session_notes_text – the session notes to be adapted into SOAP.
        template – the template to be applied.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.notes_template = template.value
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise Exception(e)

        try:
            assert len(session_notes_text or '') > 0, "Empty session_notes_text param"
            assert template != SessionNotesTemplate.FREE_FORM, "free_form is not a template that can be applied"

            soap_notes = await self._assistant_manager.adapt_session_notes_to_soap(
                therapist_id=user_id,
                session_id=session_id,
                session_notes_text=session_notes_text
            )
            return {"soap_notes": soap_notes}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=description,
                session_id=session_id
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )
