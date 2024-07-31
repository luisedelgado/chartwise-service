import json, os

from datetime import datetime

from fastapi import (APIRouter,
                     Cookie,
                     File,
                     Form,
                     HTTPException,
                     Response,
                     Request,
                     status,
                     UploadFile)
from typing import Annotated, Union

from ..api.assistant_base_class import AssistantManagerBaseClass
from ..api.audio_processing_base_class import AudioProcessingManagerBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ..data_processing.diarization_cleaner import DiarizationCleaner
from ..internal import security
from ..internal.logging import Logger
from ..internal.model import SessionNotesSource, SessionNotesTemplate
from ..internal.utilities import datetime_handler, general_utilities

class AudioProcessingRouter:

    DIARIZATION_ENDPOINT = "/v1/diarization"
    DIARIZATION_NOTIFICATION_ENDPOINT = "/v1/diarization-notification"
    NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"
    ROUTER_TAG = "audio-files"

    def __init__(self,
                auth_manager: AuthManagerBaseClass,
                assistant_manager: AssistantManagerBaseClass,
                audio_processing_manager: AudioProcessingManagerBaseClass,
                supabase_manager_factory: SupabaseFactoryBaseClass):
            self._auth_manager = auth_manager
            self._assistant_manager = assistant_manager
            self._audio_processing_manager = audio_processing_manager
            self._supabase_manager_factory = supabase_manager_factory
            self.router = APIRouter()
            self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.NOTES_TRANSCRIPTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transcribe_session_notes(response: Response,
                                           request: Request,
                                           therapist_id: Annotated[str, Form()],
                                           patient_id: Annotated[str, Form()],
                                           template: Annotated[SessionNotesTemplate, Form()],
                                           audio_file: UploadFile = File(...),
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transcribe_session_notes_internal(response=response,
                                                                 request=request,
                                                                 therapist_id=therapist_id,
                                                                 patient_id=patient_id,
                                                                 template=template,
                                                                 audio_file=audio_file,
                                                                 authorization=authorization,
                                                                 session_id=session_id)

        @self.router.post(self.DIARIZATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def diarize_session(response: Response,
                                  request: Request,
                                  session_date: Annotated[str, Form()],
                                  therapist_id: Annotated[str, Form()],
                                  patient_id: Annotated[str, Form()],
                                  client_timezone_identifier: Annotated[str, Form()],
                                  template: Annotated[SessionNotesTemplate, Form()],
                                  audio_file: UploadFile = File(...),
                                  datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                  datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._diarize_session_internal(response=response,
                                                        request=request,
                                                        session_date=session_date,
                                                        therapist_id=therapist_id,
                                                        patient_id=patient_id,
                                                        tz_identifier=client_timezone_identifier,
                                                        template=template,
                                                        audio_file=audio_file,
                                                        datastore_access_token=datastore_access_token,
                                                        datastore_refresh_token=datastore_refresh_token,
                                                        authorization=authorization,
                                                        session_id=session_id)

        @self.router.post(self.DIARIZATION_NOTIFICATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def consume_notification(request: Request):
            return await self._consume_notification_internal(request=request)

    """
    Returns the transcription created from the incoming audio file.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    therapist_id – the id of the therapist associated with the session notes.
    patient_id – the id of the patient associated with the session notes.
    template – the template to be used for generating the output.
    audio_file – the audio file for which the transcription will be created.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _transcribe_session_notes_internal(self,
                                                 response: Response,
                                                 request: Request,
                                                 therapist_id: Annotated[str, Form()],
                                                 patient_id: Annotated[str, Form()],
                                                 template: Annotated[SessionNotesTemplate, Form()],
                                                 audio_file: UploadFile,
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

        logger = Logger(supabase_manager=self._supabase_manager_factory.supabase_admin_manager())
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(session_id=session_id,
                               method=post_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Invalid therapist_id payload value"
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"

            transcript = await self._audio_processing_manager.transcribe_audio_file(assistant_manager=self._assistant_manager,
                                                                                    auth_manager=self._auth_manager,
                                                                                    template=template,
                                                                                    therapist_id=therapist_id,
                                                                                    session_id=session_id,
                                                                                    audio_file=audio_file)

            logger.log_api_response(session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            key = "soap_transcript" if template == SessionNotesTemplate.SOAP else "transcript"
            return {key: transcript}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

    """
    Returns the transcription created from the incoming audio file.
    Meant to be used for diarizing sessions.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    therapist_id – the id of the therapist associated with the session notes.
    patient_id – the id of the patient associated with the session notes.
    template – the template to be used for generating the output.
    audio_file – the audio file for which the diarized transcription will be created.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _diarize_session_internal(self,
                                        response: Response,
                                        request: Request,
                                        session_date: Annotated[str, Form()],
                                        therapist_id: Annotated[str, Form()],
                                        patient_id: Annotated[str, Form()],
                                        tz_identifier: Annotated[str, Form()],
                                        template: Annotated[SessionNotesTemplate, Form()],
                                        audio_file: UploadFile,
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

        logger = Logger(supabase_manager=self._supabase_manager_factory.supabase_admin_manager())
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(session_id=session_id,
                               patient_id=patient_id,
                               therapist_id=therapist_id,
                               method=post_api_method,
                               endpoint_name=self.DIARIZATION_ENDPOINT)

        try:
            assert general_utilities.is_valid_timezone_identifier(tz_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=session_date,
                                                  tz_identifier=tz_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert len(therapist_id or '') > 0, "Invalid therapist_id payload value"
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"

            endpoint_url = os.environ.get("ENVIRONMENT_URL") + self.DIARIZATION_NOTIFICATION_ENDPOINT
            job_id: str = await self._audio_processing_manager.diarize_audio_file(auth_manager=self._auth_manager,
                                                                                  supabase_manager=self._supabase_manager_factory.supabase_admin_manager(),
                                                                                  session_auth_token=authorization,
                                                                                  session_id=session_id,
                                                                                  audio_file=audio_file,
                                                                                  endpoint_url=endpoint_url)

            supabase_manager = self._supabase_manager_factory.supabase_user_manager(access_token=datastore_access_token,
                                                                                    refresh_token=datastore_refresh_token)
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            supabase_manager.insert(table_name="session_reports",
                                    payload={
                                        "diarization_job_id": job_id,
                                        "diarization_template": template.value,
                                        "session_date": session_date,
                                        "therapist_id": therapist_id,
                                        "patient_id": patient_id,
                                        "last_updated": now_timestamp,
                                        "source": SessionNotesSource.FULL_SESSION_RECORDING.value,
                                    })

            logs_description = f"job_id={job_id}"
            logger.log_api_response(session_id=session_id,
                                    endpoint_name=self.DIARIZATION_ENDPOINT,
                                    patient_id=patient_id,
                                    therapist_id=therapist_id,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method,
                                    description=logs_description)

            return {"job_id": job_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.DIARIZATION_ENDPOINT,
                             error_code=status_code,
                             patient_id=patient_id,
                             therapist_id=therapist_id,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

    """
    Meant to be used as a webhook so Speechmatics can notify us when a diarization operation is ready.

    Arguments:
    request – the incoming request.
    """
    async def _consume_notification_internal(self, request: Request):
        try:
            authorization = request.headers["authorization"].split()[-1]
            if not self._auth_manager.access_token_is_valid(authorization):
                raise security.AUTH_TOKEN_EXPIRED_ERROR
        except:
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        logger = Logger(supabase_manager=self._supabase_manager_factory.supabase_admin_manager())
        try:
            request_status_code = request.query_params["status"]
            id = request.query_params["id"]
            assert request_status_code.lower() == "success", f"Diarization failed for job ID {id}"

            raw_data = await request.json()
            json_data = json.loads(json.dumps(raw_data))
            job_id = json_data["job"]["id"]
            summary = json_data["summary"]["content"]
            diarization = DiarizationCleaner().clean_transcription(input=json_data["results"],
                                                                   supabase_manager=self._supabase_manager_factory.supabase_admin_manager())

            supabase_admin_manager = self._supabase_manager_factory.supabase_admin_manager()
            session_id = self._assistant_manager.update_diarization_with_notification_data(auth_manager=self._auth_manager,
                                                                                           supabase_manager=supabase_admin_manager,
                                                                                           job_id=job_id,
                                                                                           diarization_summary=summary,
                                                                                           diarization=diarization)
            logger.log_api_response(session_id=session_id,
                                    endpoint_name=self.DIARIZATION_NOTIFICATION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logger.API_METHOD_POST)
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(endpoint_name=self.DIARIZATION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=logger.API_METHOD_POST)
            logger.log_diarization_event(error_code=status_code,
                                         description=description)
            raise HTTPException(status_code=status_code, detail=description)

        return {}
