from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     File,
                     Form,
                     HTTPException,
                     Response,
                     Request,
                     status,
                     UploadFile)
from typing import Annotated, Union

from ..dependencies.api.templates import SessionNotesTemplate
from ..internal import security
from ..internal.logging import Logger
from ..internal.router_dependencies import RouterDependencies
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager

class AudioProcessingRouter:

    DIARIZATION_ENDPOINT = "/v1/diarization"
    DIARIZATION_NOTIFICATION_ENDPOINT = "/v1/diarization-notification"
    NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"
    ROUTER_TAG = "audio-files"

    def __init__(self,
                 environment: str,
                 auth_manager: AuthManager,
                 assistant_manager: AssistantManager,
                 audio_processing_manager: AudioProcessingManager,
                 router_dependencies: RouterDependencies):
            self._environment = environment
            self._auth_manager = auth_manager
            self._assistant_manager = assistant_manager
            self._audio_processing_manager = audio_processing_manager
            self._deepgram_client = router_dependencies.deepgram_client
            self._speechmatics_client = router_dependencies.speechmatics_client
            self._pinecone_client = router_dependencies.pinecone_client
            self._supabase_client_factory = router_dependencies.supabase_client_factory
            self._openai_client = router_dependencies.openai_client
            self.router = APIRouter()
            self.language_code = None
            self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.NOTES_TRANSCRIPTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transcribe_session_notes(response: Response,
                                           request: Request,
                                           background_tasks: BackgroundTasks,
                                           template: Annotated[SessionNotesTemplate, Form()],
                                           patient_id: Annotated[str, Form()],
                                           session_date: Annotated[str, Form()],
                                           client_timezone_identifier: Annotated[str, Form()],
                                           audio_file: UploadFile = File(...),
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                           datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transcribe_session_notes_internal(response=response,
                                                                 request=request,
                                                                 background_tasks=background_tasks,
                                                                 template=template,
                                                                 patient_id=patient_id,
                                                                 session_date=session_date,
                                                                 client_timezone_identifier=client_timezone_identifier,
                                                                 audio_file=audio_file,
                                                                 authorization=authorization,
                                                                 datastore_access_token=datastore_access_token,
                                                                 datastore_refresh_token=datastore_refresh_token,
                                                                 session_id=session_id)

        @self.router.post(self.DIARIZATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def diarize_session(response: Response,
                                  request: Request,
                                  background_tasks: BackgroundTasks,
                                  template: Annotated[SessionNotesTemplate, Form()],
                                  patient_id: Annotated[str, Form()],
                                  session_date: Annotated[str, Form()],
                                  client_timezone_identifier: Annotated[str, Form()],
                                  audio_file: UploadFile = File(...),
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                  datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._diarize_session_internal(response=response,
                                                        request=request,
                                                        background_tasks=background_tasks,
                                                        template=template,
                                                        patient_id=patient_id,
                                                        session_date=session_date,
                                                        client_timezone_identifier=client_timezone_identifier,
                                                        audio_file=audio_file,
                                                        authorization=authorization,
                                                        datastore_access_token=datastore_access_token,
                                                        datastore_refresh_token=datastore_refresh_token,
                                                        session_id=session_id)

    """
    Returns the transcription created from the incoming audio file.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
    template – the template to be used for generating the output.
    patient_id – the patient id associated with the operation.
    session_date – the session date associated with the operation.
    client_timezone_identifier – the timezone associated with the client.
    audio_file – the audio file for which the transcription will be created.
    authorization – the authorization cookie, if exists.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _transcribe_session_notes_internal(self,
                                                 response: Response,
                                                 request: Request,
                                                 background_tasks: BackgroundTasks,
                                                 template: Annotated[SessionNotesTemplate, Form()],
                                                 patient_id: Annotated[str, Form()],
                                                 session_date: Annotated[str, Form()],
                                                 client_timezone_identifier: Annotated[str, Form()],
                                                 audio_file: UploadFile,
                                                 authorization: Annotated[Union[str, None], Cookie()],
                                                 datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()],
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
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=post_api_method,
                               therapist_id=therapist_id,
                               endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=session_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT,
                                                  tz_identifier=client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            self.language_code = (self.language_code if self.language_code is not None
                                  else general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client))
            session_report_id = await self._audio_processing_manager.transcribe_audio_file(background_tasks=background_tasks,
                                                                                           assistant_manager=self._assistant_manager,
                                                                                           openai_client=self._openai_client,
                                                                                           deepgram_client=self._deepgram_client,
                                                                                           supabase_client=supabase_client,
                                                                                           pinecone_client=self._pinecone_client,
                                                                                           auth_manager=self._auth_manager,
                                                                                           template=template,
                                                                                           therapist_id=therapist_id,
                                                                                           session_id=session_id,
                                                                                           audio_file=audio_file,
                                                                                           logger_worker=logger,
                                                                                           session_date=session_date,
                                                                                           patient_id=patient_id,
                                                                                           environment=self._environment,
                                                                                           language_code=self.language_code)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(background_tasks=background_tasks,
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
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
    template – the template to be used for generating the output.
    patient_id – the patient id associated with the operation.
    session_date – the session date associated with the operation.
    client_timezone_identifier – the timezone associated with the client.
    audio_file – the audio file for which the transcription will be created.
    authorization – the authorization cookie, if exists.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _diarize_session_internal(self,
                                        response: Response,
                                        request: Request,
                                        background_tasks: BackgroundTasks,
                                        template: Annotated[SessionNotesTemplate, Form()],
                                        patient_id: Annotated[str, Form()],
                                        session_date: Annotated[str, Form()],
                                        client_timezone_identifier: Annotated[str, Form()],
                                        audio_file: UploadFile,
                                        authorization: Annotated[Union[str, None], Cookie()],
                                        datastore_access_token: Annotated[Union[str, None], Cookie()],
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()],
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
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=post_api_method,
                               therapist_id=therapist_id,
                               endpoint_name=self.DIARIZATION_ENDPOINT)

        try:
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=session_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT,
                                                  tz_identifier=client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            self.language_code = (self.language_code if self.language_code is not None
                                  else general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client))
            session_report_id = await self._audio_processing_manager.transcribe_audio_file(background_tasks=background_tasks,
                                                                                           assistant_manager=self._assistant_manager,
                                                                                           auth_manager=self._auth_manager,
                                                                                           openai_client=self._openai_client,
                                                                                           deepgram_client=self._deepgram_client,
                                                                                           supabase_client=supabase_client,
                                                                                           pinecone_client=self._pinecone_client,
                                                                                           template=template,
                                                                                           therapist_id=therapist_id,
                                                                                           session_date=session_date,
                                                                                           patient_id=patient_id,
                                                                                           session_id=session_id,
                                                                                           audio_file=audio_file,
                                                                                           logger_worker=logger,
                                                                                           environment=self._environment,
                                                                                           language_code=self.language_code,
                                                                                           diarize=True)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    endpoint_name=self.DIARIZATION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.DIARIZATION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)
