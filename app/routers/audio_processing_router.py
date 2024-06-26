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

from ..data_processing.diarization_cleaner import DiarizationCleaner
from ..internal import logging, model, security
from ..internal.utilities import datetime_handler
from ..managers.manager_factory import ManagerFactory

DIARIZATION_ENDPOINT = "/v1/diarization"
DIARIZATION_NOTIFICATION_ENDPOINT = "/v1/diarization-notification"
NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"

router = APIRouter()
environment = ""

"""
Returns the transcription created from the incoming audio file.

Arguments:
response – the response model with which to create the final response.
therapist_id – the id of the therapist associated with the session notes.
patient_id – the id of the patient associated with the session notes.
audio_file – the audio file for which the transcription will be created.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(NOTES_TRANSCRIPTION_ENDPOINT, tags=["audio-files"])
async def transcribe_session_notes(response: Response,
                                   therapist_id: Annotated[str, Form()],
                                   patient_id: Annotated[str, Form()],
                                   audio_file: UploadFile = File(...),
                                   authorization: Annotated[Union[str, None], Cookie()] = None,
                                   current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            method=logging.API_METHOD_POST,
                            therapist_id=therapist_id,
                            patient_id=patient_id,
                            endpoint_name=NOTES_TRANSCRIPTION_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        audio_processing_manager = ManagerFactory.create_audio_processing_manager(environment)
        auth_manager = ManagerFactory.create_auth_manager(environment)
        transcript = await audio_processing_manager.transcribe_audio_file(auth_manager=auth_manager,
                                                                          audio_file=audio_file)

        logging.log_api_response(session_id=session_id,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=NOTES_TRANSCRIPTION_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_POST)

        return {"transcript": transcript}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=NOTES_TRANSCRIPTION_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=logging.API_METHOD_POST)
        raise HTTPException(status_code=status_code, detail=description)

"""
Returns the transcription created from the incoming audio file.
Meant to be used for diarizing sessions.

Arguments:
response – the response model with which to create the final response.
therapist_id – the id of the therapist associated with the session notes.
patient_id – the id of the patient associated with the session notes.
audio_file – the audio file for which the diarized transcription will be created.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(DIARIZATION_ENDPOINT, tags=["audio-files"])
async def diarize_session(response: Response,
                          session_date: Annotated[str, Form()],
                          therapist_id: Annotated[str, Form()],
                          patient_id: Annotated[str, Form()],
                          audio_file: UploadFile = File(...),
                          authorization: Annotated[Union[str, None], Cookie()] = None,
                          current_session_id: Annotated[Union[str, None], Cookie()] = None,):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=patient_id,
                            therapist_id=therapist_id,
                            method=logging.API_METHOD_POST,
                            endpoint_name=DIARIZATION_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        assert datetime_handler.is_valid_date(session_date), "Invalid date. The expected format is mm-dd-yyyy"

        endpoint_url = os.environ.get("ENVIRONMENT_URL") + DIARIZATION_NOTIFICATION_ENDPOINT
        audio_processing_manager = ManagerFactory.create_audio_processing_manager(environment)
        auth_manager = ManagerFactory.create_auth_manager(environment)
        job_id: str = await audio_processing_manager.diarize_audio_file(auth_manager=auth_manager,
                                                                        session_auth_token=authorization,
                                                                        audio_file=audio_file,
                                                                        endpoint_url=endpoint_url)

        now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
        datastore_client = auth_manager.datastore_admin_instance()
        datastore_client.table('session_reports').insert({
            "session_diarization_job_id": job_id,
            "session_date": session_date,
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "last_updated": now_timestamp,
            "source": "full_session_recording",
        }).execute()

        logging.log_api_response(session_id=session_id,
                                endpoint_name=DIARIZATION_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_POST)

        return {"job_id": job_id}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=DIARIZATION_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=logging.API_METHOD_POST)
        raise HTTPException(status_code=status_code, detail=description)

"""
Meant to be used as a webhook so Speechmatics can notify us when a diarization operation is ready.

Arguments:
request – the incoming request.
"""
@router.post(DIARIZATION_NOTIFICATION_ENDPOINT, tags=["audio-files"])
async def consume_notification(request: Request):
    try:
        authorization = request.headers["authorization"].split()[-1]
        if not security.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR
    except:
        raise security.TOKEN_EXPIRED_ERROR

    try:
        status_code = request.query_params["status"]
        id = request.query_params["id"]
        assert status_code.lower() == "success", f"Diarization failed for job ID {id}"

        datastore_client = ManagerFactory.create_auth_manager(environment).datastore_admin_instance()

        raw_data = await request.json()
        json_data = json.loads(json.dumps(raw_data))
        job_id = json_data["job"]["id"]
        summary = json_data["summary"]["content"]
        diarization = DiarizationCleaner().clean_transcription(json_data["results"])

        now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
        datastore_client.table('session_reports').update({
            "notes_text": summary,
            "session_diarization": diarization,
            "last_updated": now_timestamp,
        }).eq('session_diarization_job_id', job_id).execute()

    except Exception as e:
        description = str(e)
        status_code = status.HTTP_417_EXPECTATION_FAILED if type(e) is not HTTPException else e.status_code
        logging.log_diarization_event(error_code=status_code, description=description)
        raise HTTPException(status_code=status_code, detail=description)

    return {}