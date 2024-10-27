from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     File,
                     Form,
                     Header,
                     HTTPException,
                     Response,
                     status,
                     UploadFile)
from typing import Annotated, Union

from ..dependencies.api.templates import SessionNotesTemplate
from ..internal import security
from ..internal.dependency_container import dependency_container
from ..internal.logging import (API_METHOD_POST,
                                log_api_request,
                                log_api_response,
                                log_error)
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager

class AudioProcessingRouter:

    DIARIZATION_ENDPOINT = "/v1/diarization"
    DIARIZATION_NOTIFICATION_ENDPOINT = "/v1/diarization-notification"
    NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"
    ROUTER_TAG = "audio-files"

    def __init__(self, environment: str):
            self._environment = environment
            self._auth_manager = AuthManager()
            self._assistant_manager = AssistantManager()
            self._audio_processing_manager = AudioProcessingManager()
            self.router = APIRouter()
            self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.NOTES_TRANSCRIPTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transcribe_session_notes(response: Response,
                                           background_tasks: BackgroundTasks,
                                           template: Annotated[SessionNotesTemplate, Form()],
                                           patient_id: Annotated[str, Form()],
                                           session_date: Annotated[str, Form()],
                                           client_timezone_identifier: Annotated[str, Form()],
                                           store_access_token: Annotated[str | None, Header()] = None,
                                           store_refresh_token: Annotated[str | None, Header()] = None,
                                           audio_file: UploadFile = File(...),
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transcribe_session_notes_internal(response=response,
                                                                 background_tasks=background_tasks,
                                                                 template=template,
                                                                 patient_id=patient_id,
                                                                 session_date=session_date,
                                                                 client_timezone_identifier=client_timezone_identifier,
                                                                 audio_file=audio_file,
                                                                 authorization=authorization,
                                                                 store_access_token=store_access_token,
                                                                 store_refresh_token=store_refresh_token,
                                                                 session_id=session_id)

        @self.router.post(self.DIARIZATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def diarize_session(response: Response,
                                  background_tasks: BackgroundTasks,
                                  template: Annotated[SessionNotesTemplate, Form()],
                                  patient_id: Annotated[str, Form()],
                                  session_date: Annotated[str, Form()],
                                  client_timezone_identifier: Annotated[str, Form()],
                                  store_access_token: Annotated[str | None, Header()] = None,
                                  store_refresh_token: Annotated[str | None, Header()] = None,
                                  audio_file: UploadFile = File(...),
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._diarize_session_internal(response=response,
                                                        background_tasks=background_tasks,
                                                        template=template,
                                                        patient_id=patient_id,
                                                        session_date=session_date,
                                                        client_timezone_identifier=client_timezone_identifier,
                                                        audio_file=audio_file,
                                                        authorization=authorization,
                                                        store_access_token=store_access_token,
                                                        store_refresh_token=store_refresh_token,
                                                        session_id=session_id)

    """
    Returns the transcription created from the incoming audio file.

    Arguments:
    response – the response model with which to create the final response.
    background_tasks – object for scheduling concurrent tasks.
    template – the template to be used for generating the output.
    patient_id – the patient id associated with the operation.
    session_date – the session date associated with the operation.
    client_timezone_identifier – the timezone associated with the client.
    audio_file – the audio file for which the transcription will be created.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _transcribe_session_notes_internal(self,
                                                 response: Response,
                                                 background_tasks: BackgroundTasks,
                                                 template: Annotated[SessionNotesTemplate, Form()],
                                                 patient_id: Annotated[str, Form()],
                                                 session_date: Annotated[str, Form()],
                                                 client_timezone_identifier: Annotated[str, Form()],
                                                 audio_file: UploadFile,
                                                 store_access_token: Annotated[str | None, Header()],
                                                 store_refresh_token: Annotated[str | None, Header()],
                                                 authorization: Annotated[Union[str, None], Cookie()],
                                                 session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        post_api_method = API_METHOD_POST
        description = "".join([
            "template=\"",
            f"{template.value or ''}\";",
            "session_date=\"",
            f"{session_date or ''}\";",
            "client_timezone=\"",
            f"{client_timezone_identifier or ''}\""
        ])
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=post_api_method,
                        description=description,
                        patient_id=patient_id,
                        endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT)

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=post_api_method,
                      patient_id=patient_id)
            raise security.STORE_TOKENS_ERROR

        try:
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=session_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT,
                                                  tz_identifier=client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
            session_report_id = await self._audio_processing_manager.transcribe_audio_file(background_tasks=background_tasks,
                                                                                           assistant_manager=self._assistant_manager,
                                                                                           supabase_client=supabase_client,
                                                                                           auth_manager=self._auth_manager,
                                                                                           template=template,
                                                                                           therapist_id=therapist_id,
                                                                                           session_id=session_id,
                                                                                           audio_file=audio_file,
                                                                                           session_date=session_date,
                                                                                           patient_id=patient_id,
                                                                                           environment=self._environment,
                                                                                           language_code=language_code)

            log_api_response(background_tasks=background_tasks,
                             session_id=session_id,
                             therapist_id=therapist_id,
                             endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=post_api_method)

            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

    """
    Returns the transcription created from the incoming audio file.

    Arguments:
    response – the response model with which to create the final response.
    background_tasks – object for scheduling concurrent tasks.
    template – the template to be used for generating the output.
    patient_id – the patient id associated with the operation.
    session_date – the session date associated with the operation.
    client_timezone_identifier – the timezone associated with the client.
    audio_file – the audio file for which the transcription will be created.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _diarize_session_internal(self,
                                        response: Response,
                                        background_tasks: BackgroundTasks,
                                        template: Annotated[SessionNotesTemplate, Form()],
                                        patient_id: Annotated[str, Form()],
                                        session_date: Annotated[str, Form()],
                                        client_timezone_identifier: Annotated[str, Form()],
                                        audio_file: UploadFile,
                                        store_access_token: Annotated[str | None, Header()],
                                        store_refresh_token: Annotated[str | None, Header()],
                                        authorization: Annotated[Union[str, None], Cookie()],
                                        session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        description = "".join([
            "template=\"",
            f"{template.value or ''}\";",
            "session_date=\"",
            f"{session_date or ''}\";",
            "client_timezone=\"",
            f"{client_timezone_identifier or ''}\""
        ])
        post_api_method = API_METHOD_POST
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=post_api_method,
                        description=description,
                        patient_id=patient_id,
                        endpoint_name=self.DIARIZATION_ENDPOINT)

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.DIARIZATION_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=post_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=session_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT,
                                                  tz_identifier=client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.DIARIZATION_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

        try:
            session_report_id = await self._audio_processing_manager.transcribe_audio_file(background_tasks=background_tasks,
                                                                                           assistant_manager=self._assistant_manager,
                                                                                           auth_manager=self._auth_manager,
                                                                                           supabase_client=supabase_client,
                                                                                           template=template,
                                                                                           therapist_id=therapist_id,
                                                                                           session_date=session_date,
                                                                                           patient_id=patient_id,
                                                                                           session_id=session_id,
                                                                                           audio_file=audio_file,
                                                                                           environment=self._environment,
                                                                                           language_code=language_code,
                                                                                           diarize=True)

            log_api_response(background_tasks=background_tasks,
                             session_id=session_id,
                             therapist_id=therapist_id,
                             endpoint_name=self.DIARIZATION_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=post_api_method)

            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.DIARIZATION_ENDPOINT,
                      error_code=status_code,
                      description=description,
                      method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)
