import json, os

from datetime import datetime

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

from ..data_processing.diarization_cleaner import DiarizationCleaner
from ..dependencies.api.templates import SessionNotesTemplate
from ..internal import security
from ..internal.logging import Logger
from ..internal.router_dependencies import RouterDependencies
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import AssistantManager, SessionNotesSource
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager

class AudioProcessingRouter:

    DIARIZATION_ENDPOINT = "/v1/diarization"
    DIARIZATION_NOTIFICATION_ENDPOINT = "/v1/diarization-notification"
    NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"
    ROUTER_TAG = "audio-files"

    def __init__(self,
                auth_manager: AuthManager,
                assistant_manager: AssistantManager,
                audio_processing_manager: AudioProcessingManager,
                router_dependencies: RouterDependencies):
            self._auth_manager = auth_manager
            self._assistant_manager = assistant_manager
            self._audio_processing_manager = audio_processing_manager
            self._deepgram_client = router_dependencies.deepgram_client
            self._speechmatics_client = router_dependencies.speechmatics_client
            self._pinecone_client = router_dependencies.pinecone_client
            self._supabase_client_factory = router_dependencies.supabase_client_factory
            self._openai_client = router_dependencies.openai_client
            self.router = APIRouter()
            self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.NOTES_TRANSCRIPTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transcribe_session_notes(response: Response,
                                           request: Request,
                                           background_tasks: BackgroundTasks,
                                           patient_id: Annotated[str, Form()],
                                           template: Annotated[SessionNotesTemplate, Form()],
                                           audio_file: UploadFile = File(...),
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                           datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transcribe_session_notes_internal(response=response,
                                                                 request=request,
                                                                 background_tasks=background_tasks,
                                                                 patient_id=patient_id,
                                                                 template=template,
                                                                 audio_file=audio_file,
                                                                 authorization=authorization,
                                                                 datastore_access_token=datastore_access_token,
                                                                 datastore_refresh_token=datastore_refresh_token,
                                                                 session_id=session_id)

        @self.router.post(self.DIARIZATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def diarize_session(response: Response,
                                  request: Request,
                                  background_tasks: BackgroundTasks,
                                  session_date: Annotated[str, Form()],
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
                                                        background_tasks=background_tasks,
                                                        session_date=session_date,
                                                        patient_id=patient_id,
                                                        tz_identifier=client_timezone_identifier,
                                                        template=template,
                                                        audio_file=audio_file,
                                                        datastore_access_token=datastore_access_token,
                                                        datastore_refresh_token=datastore_refresh_token,
                                                        authorization=authorization,
                                                        session_id=session_id)

        @self.router.post(self.DIARIZATION_NOTIFICATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def consume_notification(request: Request, background_tasks: BackgroundTasks):
            return await self._consume_notification_internal(request=request, background_tasks=background_tasks)

    """
    Returns the transcription created from the incoming audio file.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
    patient_id – the id of the patient associated with the session notes.
    template – the template to be used for generating the output.
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
                                                 patient_id: Annotated[str, Form()],
                                                 template: Annotated[SessionNotesTemplate, Form()],
                                                 audio_file: UploadFile,
                                                 authorization: Annotated[Union[str, None], Cookie()],
                                                 datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                 datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                 session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

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
                               patient_id=patient_id,
                               endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Invalid therapist_id payload value"
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"

            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            transcript = await self._audio_processing_manager.transcribe_audio_file(assistant_manager=self._assistant_manager,
                                                                                    openai_client=self._openai_client,
                                                                                    deepgram_client=self._deepgram_client,
                                                                                    auth_manager=self._auth_manager,
                                                                                    template=template,
                                                                                    therapist_id=therapist_id,
                                                                                    session_id=session_id,
                                                                                    audio_file=audio_file)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
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
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
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
                                        background_tasks: BackgroundTasks,
                                        session_date: Annotated[str, Form()],
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
                               patient_id=patient_id,
                               therapist_id=therapist_id,
                               method=post_api_method,
                               endpoint_name=self.DIARIZATION_ENDPOINT)

        try:
            assert general_utilities.is_valid_timezone_identifier(tz_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=session_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT,
                                                  tz_identifier=tz_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert len(therapist_id or '') > 0, "Invalid therapist_id payload value"
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"

            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            endpoint_url = os.environ.get("ENVIRONMENT_URL") + self.DIARIZATION_NOTIFICATION_ENDPOINT
            job_id: str = await self._audio_processing_manager.diarize_audio_file(auth_manager=self._auth_manager,
                                                                                  therapist_id=therapist_id,
                                                                                  background_tasks=background_tasks,
                                                                                  supabase_client_factory=self._supabase_client_factory,
                                                                                  session_auth_token=authorization,
                                                                                  speechmatics_client=self._speechmatics_client,
                                                                                  session_id=session_id,
                                                                                  audio_file=audio_file,
                                                                                  endpoint_url=endpoint_url)

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            supabase_client.insert(table_name="session_reports",
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
            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
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
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
    """
    async def _consume_notification_internal(self, request: Request, background_tasks: BackgroundTasks):
        try:
            authorization = request.headers["authorization"].split()[-1]
            if not self._auth_manager.access_token_is_valid(authorization):
                raise security.AUTH_TOKEN_EXPIRED_ERROR
        except:
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        try:
            request_status_code = request.query_params["status"]
            id = request.query_params["id"]
            assert request_status_code.lower() == "success", f"Diarization failed for job ID {id}"

            raw_data = await request.json()
            json_data = json.loads(json.dumps(raw_data))
            job_id = json_data["job"]["id"]

            supabase_admin_client = self._supabase_client_factory.supabase_admin_client()
            diarization_query = supabase_admin_client.select(fields="*",
                                                             filters={
                                                                 'job_id': job_id
                                                             },
                                                             table_name="diarization_logs")
            assert (0 != len((diarization_query).data)), "No data was found for this diarization operation."
            diarization_query_dict = diarization_query.dict()
            therapist_id = diarization_query_dict['data'][0]['therapist_id']
            session_id = diarization_query_dict['data'][0]['session_id']

            diarization = DiarizationCleaner().clean_transcription(background_tasks=background_tasks,
                                                                   therapist_id=therapist_id,
                                                                   input=json_data["results"],
                                                                   supabase_client_factory=self._supabase_client_factory)


            summary = json_data["summary"]["content"]
            await self._assistant_manager.update_diarization_with_notification_data(auth_manager=self._auth_manager,
                                                                                    supabase_client=supabase_admin_client,
                                                                                    openai_client=self._openai_client,
                                                                                    pinecone_client=self._pinecone_client,
                                                                                    job_id=job_id,
                                                                                    session_id=session_id,
                                                                                    diarization_summary=summary,
                                                                                    diarization=diarization)
            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.DIARIZATION_NOTIFICATION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logger.API_METHOD_POST)
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(background_tasks=background_tasks,
                             endpoint_name=self.DIARIZATION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=logger.API_METHOD_POST)
            logger.log_diarization_event(background_tasks=background_tasks,
                                         error_code=status_code,
                                         description=description)
            raise HTTPException(status_code=status_code, detail=description)

        return {}
