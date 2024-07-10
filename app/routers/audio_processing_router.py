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
from supabase import Client
from typing import Annotated, Union

from ..api.assistant_base_class import AssistantManagerBaseClass
from ..api.audio_processing_base_class import AudioProcessingManagerBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..data_processing.diarization_cleaner import DiarizationCleaner
from ..internal import logging, model, security
from ..internal.utilities import datetime_handler

class AudioProcessingRouter:

    DIARIZATION_ENDPOINT = "/v1/diarization"
    DIARIZATION_NOTIFICATION_ENDPOINT = "/v1/diarization-notification"
    NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"
    ROUTER_TAG = "audio-files"

    def __init__(self,
                auth_manager: AuthManagerBaseClass,
                assistant_manager: AssistantManagerBaseClass,
                audio_processing_manager: AudioProcessingManagerBaseClass):
            self._auth_manager = auth_manager
            self._assistant_manager = assistant_manager
            self._audio_processing_manager = audio_processing_manager
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
                                           audio_file: UploadFile = File(...),
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transcribe_session_notes_internal(response=response,
                                                                 request=request,
                                                                 therapist_id=therapist_id,
                                                                 patient_id=patient_id,
                                                                 audio_file=audio_file,
                                                                 authorization=authorization,
                                                                 current_session_id=current_session_id)

        @self.router.post(self.DIARIZATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def diarize_session(response: Response,
                                  request: Request,
                                  session_date: Annotated[str, Form()],
                                  therapist_id: Annotated[str, Form()],
                                  patient_id: Annotated[str, Form()],
                                  audio_file: UploadFile = File(...),
                                  datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                  datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._diarize_session_internal(response=response,
                                                        request=request,
                                                        session_date=session_date,
                                                        therapist_id=therapist_id,
                                                        patient_id=patient_id,
                                                        audio_file=audio_file,
                                                        datastore_access_token=datastore_access_token,
                                                        datastore_refresh_token=datastore_refresh_token,
                                                        authorization=authorization,
                                                        current_session_id=current_session_id)

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
    audio_file – the audio file for which the transcription will be created.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _transcribe_session_notes_internal(self,
                                                 response: Response,
                                                 request: Request,
                                                 therapist_id: Annotated[str, Form()],
                                                 patient_id: Annotated[str, Form()],
                                                 audio_file: UploadFile,
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
                                method=logging.API_METHOD_POST,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT)

        try:
            transcript = await self._audio_processing_manager.transcribe_audio_file(auth_manager=self._auth_manager,
                                                                                    audio_file=audio_file)

            logging.log_api_response(session_id=session_id,
                                     therapist_id=therapist_id,
                                     patient_id=patient_id,
                                     endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_POST)

            return {"transcript": transcript}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            endpoint_name=self.NOTES_TRANSCRIPTION_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code, detail=description)

    """
    Returns the transcription created from the incoming audio file.
    Meant to be used for diarizing sessions.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    therapist_id – the id of the therapist associated with the session notes.
    patient_id – the id of the patient associated with the session notes.
    audio_file – the audio file for which the diarized transcription will be created.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _diarize_session_internal(self,
                                        response: Response,
                                        request: Request,
                                        session_date: Annotated[str, Form()],
                                        therapist_id: Annotated[str, Form()],
                                        patient_id: Annotated[str, Form()],
                                        audio_file: UploadFile,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()],
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                        authorization: Annotated[Union[str, None], Cookie()],
                                        current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user_id=therapist_id,
                                                                                                      request=request,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                patient_id=patient_id,
                                therapist_id=therapist_id,
                                method=logging.API_METHOD_POST,
                                endpoint_name=self.DIARIZATION_ENDPOINT)

        try:
            assert datetime_handler.is_valid_date(session_date), "Invalid date format. The expected format is mm-dd-yyyy"

            endpoint_url = os.environ.get("ENVIRONMENT_URL") + self.DIARIZATION_NOTIFICATION_ENDPOINT
            job_id: str = await self._audio_processing_manager.diarize_audio_file(auth_manager=self._auth_manager,
                                                                                  session_auth_token=authorization,
                                                                                  audio_file=audio_file,
                                                                                  endpoint_url=endpoint_url)

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            datastore_client: Client = self._auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                                  refresh_token=datastore_refresh_token)
            datastore_client.table('session_reports').insert({
                "session_diarization_job_id": job_id,
                "session_date": session_date,
                "therapist_id": therapist_id,
                "patient_id": patient_id,
                "last_updated": now_timestamp,
                "source": "full_session_recording",
            }).execute()

            logging.log_api_response(session_id=session_id,
                                    endpoint_name=self.DIARIZATION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST)

            return {"job_id": job_id}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            endpoint_name=self.DIARIZATION_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
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

        try:
            status_code = request.query_params["status"]
            id = request.query_params["id"]
            assert status_code.lower() == "success", f"Diarization failed for job ID {id}"

            raw_data = await request.json()
            json_data = json.loads(json.dumps(raw_data))
            job_id = json_data["job"]["id"]
            summary = json_data["summary"]["content"]
            diarization = DiarizationCleaner().clean_transcription(json_data["results"])

            self._assistant_manager.update_diarization_with_notification_data(auth_manager=self._auth_manager,
                                                                              job_id=job_id,
                                                                              summary=summary,
                                                                              diarization=diarization)
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_417_EXPECTATION_FAILED if type(e) is not HTTPException else e.status_code
            logging.log_diarization_event(error_code=status_code, description=description)
            raise HTTPException(status_code=status_code, detail=description)

        return {}
