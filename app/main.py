import json

from datetime import datetime
from dataclasses import field
from fastapi import (
    Cookie,
    Depends,
    Header,
    HTTPException,
    FastAPI,
    File,
    Form,
    Request,
    Response,
    status,
    UploadFile)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from langcodes import Language
from supabase import Client
from typing import Annotated, Union

from .assistant import query as query_handler
from .assistant import vector_writer
from .data_processing.diarization_cleaner import DiarizationCleaner
from .internal import (endpoints,
                       library_clients,
                       logging,
                       models,
                       security,
                       utilities,)

TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

app = FastAPI()

origins = [
    # Daniel Daza development
    "https://localhost:5173",
    library_clients.SPEECHMATICS_NOTIFICATION_IPS,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Assistant endpoints

"""
Stores a new session report.

Arguments:
body – the incoming request body.
response – the response model with which to create the final response.
authorization – the authorization cookie, if exists.
current_session_id – the session_id cookie, if exists.
"""
@app.post(endpoints.SESSIONS_ENDPOINT)
async def insert_new_session(body: models.SessionNotesInsert,
                             response: Response,
                             authorization: Annotated[Union[str, None], Cookie()] = None,
                             current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=body.patient_id,
                            therapist_id=body.therapist_id,
                            endpoint_name=endpoints.SESSIONS_ENDPOINT,
                            method=endpoints.API_METHOD_POST,
                            auth_entity=current_user.username)

    try:
        assert utilities.is_valid_date(body.date), "Invalid date. The expected format is mm-dd-yyyy"

        supabase_client = library_clients.supabase_user_instance(body.supabase_access_token,
                                                                 body.supabase_refresh_token)
        now_timestamp = datetime.now().strftime(utilities.DATE_TIME_FORMAT)
        supabase_client.table('session_reports').insert({
            "notes_text": body.text,
            "session_date": body.date,
            "patient_id": body.patient_id,
            "source": body.source,
            "last_updated": now_timestamp,
            "therapist_id": body.therapist_id}).execute()

        # Upload vector embeddings
        vector_writer.insert_session_vectors(index_id=body.therapist_id,
                                             namespace=body.patient_id,
                                             text=body.text,
                                             date=body.date)
        logging.log_api_response(session_id=session_id,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=endpoints.SESSIONS_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_POST)

        return {}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=body.therapist_id,
                          patient_id=body.patient_id,
                          endpoint_name=endpoints.SESSIONS_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_POST)
        raise HTTPException(status_code=status_code,
                            detail=description)

"""
Updates a session report.

Arguments:
body – the incoming request body.
response – the response model with which to create the final response.
authorization – the authorization cookie, if exists.
current_session_id – the session_id cookie, if exists.
"""
@app.put(endpoints.SESSIONS_ENDPOINT)
async def update_session(body: models.SessionNotesUpdate,
                         response: Response,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=body.patient_id,
                            therapist_id=body.therapist_id,
                            endpoint_name=endpoints.SESSIONS_ENDPOINT,
                            method=endpoints.API_METHOD_PUT,
                            auth_entity=current_user.username)

    try:
        supabase_client = library_clients.supabase_user_instance(body.supabase_access_token,
                                                                 body.supabase_refresh_token)

        now_timestamp = datetime.now().strftime(utilities.DATE_TIME_FORMAT)
        update_result = supabase_client.table('session_reports').update({
            "notes_text": body.text,
            "last_updated": now_timestamp,
            "session_diarization": body.diarization,
        }).eq('id', body.session_notes_id).execute()

        session_date_raw = update_result.dict()['data'][0]['session_date']
        session_date_formatted = utilities.convert_to_internal_date_format(session_date_raw)

        # Upload vector embeddings
        vector_writer.update_session_vectors(index_id=body.therapist_id,
                                             namespace=body.patient_id,
                                             text=body.text,
                                             date=session_date_formatted)

        logging.log_api_response(session_id=session_id,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=endpoints.SESSIONS_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_PUT)

        return {}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=body.therapist_id,
                          patient_id=body.patient_id,
                          endpoint_name=endpoints.SESSIONS_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_PUT)
        raise HTTPException(status_code=status_code,
                            detail=description)

"""
Deletes a session report.

Arguments:
body – the incoming request body.
response – the response model with which to create the final response.
authorization – the authorization cookie, if exists.
current_session_id – the session_id cookie, if exists.
"""
@app.delete(endpoints.SESSIONS_ENDPOINT)
async def delete_session(body: models.SessionNotesDelete,
                         response: Response,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None,):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=body.patient_id,
                            therapist_id=body.therapist_id,
                            endpoint_name=endpoints.SESSIONS_ENDPOINT,
                            method=endpoints.API_METHOD_DELETE,
                            auth_entity=current_user.username)

    try:
        supabase_client = library_clients.supabase_user_instance(body.supabase_access_token,
                                                                 body.supabase_refresh_token)

        delete_result = supabase_client.table('session_reports').delete().eq('id', body.session_notes_id).execute()

        session_date_raw = delete_result.dict()['data'][0]['session_date']
        session_date_formatted = utilities.convert_to_internal_date_format(session_date_raw)

        # Delete vector embeddings
        vector_writer.delete_session_vectors(index_id=body.therapist_id,
                                             namespace=body.patient_id,
                                             date=session_date_formatted)

        logging.log_api_response(session_id=session_id,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=endpoints.SESSIONS_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_DELETE)

        return {}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=body.therapist_id,
                          patient_id=body.patient_id,
                          endpoint_name=endpoints.SESSIONS_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_DELETE)
        raise HTTPException(status_code=status_code,
                            detail=description)

"""
Executes a query to our assistant system.
Returns the query response.

Arguments:
query – the query that will be executed.
response – the response model with which to create the final response.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.QUERIES_ENDPOINT)
async def execute_assistant_query(query: models.AssistantQuery,
                                  response: Response,
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            therapist_id=query.therapist_id,
                            patient_id=query.patient_id,
                            endpoint_name=endpoints.QUERIES_ENDPOINT,
                            method=endpoints.API_METHOD_POST,
                            auth_entity=current_user.username)

    try:
        assert Language.get(query.response_language_code).is_valid(), "Invalid response_language_code parameter"
        supabase_client = library_clients.supabase_user_instance(query.supabase_access_token,
                                                                 query.supabase_refresh_token)

        # Confirm that the incoming patient id is assigned to the incoming therapist id.
        patient_therapist_match = (0 != len(
            (supabase_client.from_('patients').select('*').eq('therapist_id', query.therapist_id).eq('id',
                                                                                                    query.patient_id).execute()
        ).data))

        assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          patient_id=query.patient_id,
                          endpoint_name=endpoints.QUERIES_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_POST)
        raise HTTPException(status_code=status_code,
                            detail=description)

    try:
        # Go through with the query
        response: query_handler.QueryResult = query_handler.query_store(index_id=query.therapist_id,
                                                                        namespace=query.patient_id,
                                                                        input=query.text,
                                                                        response_language_code=query.response_language_code,
                                                                        session_id=session_id,
                                                                        endpoint_name=endpoints.QUERIES_ENDPOINT,
                                                                        method=endpoints.API_METHOD_POST)

        assert response.status_code != status.HTTP_200_OK, "Something went wrong when executing the query"

        logging.log_api_response(session_id=session_id,
                                therapist_id=query.therapist_id,
                                patient_id=query.patient_id,
                                endpoint_name=endpoints.QUERIES_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_POST)

        return {"response": response.response_token}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                        therapist_id=query.therapist_id,
                        patient_id=query.patient_id,
                        endpoint_name=endpoints.QUERIES_ENDPOINT,
                        error_code=status_code,
                        description=description,
                        method=endpoints.API_METHOD_POST)
        raise HTTPException(status_code=status_code,
                            detail=description)

"""
Returns a new greeting to the user.

Arguments:
response – the response model used for the final response that will be returned.
addressing_name – the name to be used for addressing the user in the greeting.
response_language_code – the language code to be used for creating the greeting.
client_tz_identifier – the timezone identifier used to fetch the client's weekday.
therapist_id – the id of the therapist for which the greeting is being created.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.GREETINGS_ENDPOINT)
async def fetch_greeting(response: Response,
                         addressing_name: Annotated[str, Form()],
                         response_language_code: Annotated[str, Form()],
                         client_tz_identifier: Annotated[str, Form()],
                         therapist_id: Annotated[str, Form()],
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logs_description = ''.join(['language_code:',
                                response_language_code,
                                ';tz_identifier:',
                                client_tz_identifier])
    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            therapist_id=therapist_id,
                            endpoint_name=endpoints.GREETINGS_ENDPOINT,
                            auth_entity=current_user.username,
                            description=logs_description)

    try:
        assert utilities.is_valid_timezone_identifier(client_tz_identifier), "Invalid timezone identifier parameter"
        assert Language.get(response_language_code).is_valid(), "Invalid response_language_code parameter"

        result = query_handler.create_greeting(name=addressing_name,
                                               language_code=response_language_code,
                                               tz_identifier=client_tz_identifier,
                                               session_id=session_id,
                                               endpoint_name=endpoints.GREETINGS_ENDPOINT,
                                               therapist_id=therapist_id,
                                               method=endpoints.API_METHOD_POST)
        assert result.status_code == status.HTTP_200_OK

        logging.log_api_response(session_id=session_id,
                                endpoint_name=endpoints.GREETINGS_ENDPOINT,
                                therapist_id=therapist_id,
                                http_status_code=status.HTTP_200_OK,
                                description=logs_description,
                                method=endpoints.API_METHOD_POST)

        return {"message": result.response_token}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.GREETINGS_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_POST)
        raise HTTPException(status_code=status_code,
                            detail=description)

"""
Returns an OK status if the endpoint can be reached.

Arguments:
authorization – The authorization cookie, if exists.
"""
@app.get(endpoints.HEALTHCHECK_ENDPOINT)
def read_healthcheck(authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    return {"status": "ok"}

# Image handling endpoints

"""
Returns a document_id value associated with the file that was uploaded.

Arguments:
response – the response model with which to create the final response.
therapist_id – the id of the therapist associated with the session notes.
patient_id – the id of the patient associated with the session notes.
image – the image to be uploaded.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.IMAGE_UPLOAD_ENDPOINT)
async def upload_session_notes_image(response: Response,
                                     patient_id: Annotated[str, Form()],
                                     therapist_id: Annotated[str, Form()],
                                     image: UploadFile = File(...),
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            patient_id=patient_id,
                            therapist_id=therapist_id,
                            endpoint_name=endpoints.IMAGE_UPLOAD_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        document_id = await library_clients.upload_image_for_textraction(image)

        logging.log_api_response(session_id=session_id,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=endpoints.IMAGE_UPLOAD_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_POST)

        return {"document_id": document_id}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.IMAGE_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_POST)
        raise HTTPException(status_code=status_code, detail=description)

"""
Returns the text extracted from the incoming document_id.

Arguments:
response – the response model to be used for crafting the final response.
therapist_id – the therapist_id for the operation.
patient_id – the patient_id for the operation.
document_id – the id of the document to be textracted.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@app.get(endpoints.TEXT_EXTRACTION_ENDPOINT)
async def extract_text(response: Response,
                       therapist_id: Annotated[str, Form()],
                       patient_id: Annotated[str, Form()],
                       document_id: str = None,
                       authorization: Annotated[Union[str, None], Cookie()] = None,
                       current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_GET,
                            therapist_id=therapist_id,
                            patient_id=patient_id,
                            endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        assert len(document_id) > 0, "Didn't receive a valid document id."
        full_text = library_clients.extract_text(document_id)

        logging.log_api_response(session_id=session_id,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_GET)

        return {"extraction": full_text}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=patient_id,
                          endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_GET)
        raise HTTPException(status_code=status_code, detail=description)

# Audio handling endpoint

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
@app.post(endpoints.NOTES_TRANSCRIPTION_ENDPOINT)
async def transcribe_session_notes(response: Response,
                                   therapist_id: Annotated[str, Form()],
                                   patient_id: Annotated[str, Form()],
                                   audio_file: UploadFile = File(...),
                                   authorization: Annotated[Union[str, None], Cookie()] = None,
                                   current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            therapist_id=therapist_id,
                            patient_id=patient_id,
                            endpoint_name=endpoints.NOTES_TRANSCRIPTION_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        transcript = await library_clients.transcribe_audio_file(audio_file)

        logging.log_api_response(session_id=session_id,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=endpoints.NOTES_TRANSCRIPTION_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_POST)

        return {"transcript": transcript}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.NOTES_TRANSCRIPTION_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_POST)
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
@app.post(endpoints.DIARIZATION_ENDPOINT)
async def diarize_session(response: Response,
                          session_date: Annotated[str, Form()],
                          therapist_id: Annotated[str, Form()],
                          patient_id: Annotated[str, Form()],
                          audio_file: UploadFile = File(...),
                          authorization: Annotated[Union[str, None], Cookie()] = None,
                          current_session_id: Annotated[Union[str, None], Cookie()] = None,):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=patient_id,
                            therapist_id=therapist_id,
                            method=endpoints.API_METHOD_POST,
                            endpoint_name=endpoints.DIARIZATION_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        assert utilities.is_valid_date(session_date), "Invalid date. The expected format is mm-dd-yyyy"

        supabase_client = library_clients.supabase_admin_instance()
        job_id: str = await library_clients.diarize_audio_file(session_auth_token=authorization,
                                                               audio_file=audio_file)

        now_timestamp = datetime.now().strftime(utilities.DATE_TIME_FORMAT)
        supabase_client.table('session_reports').insert({
            "session_diarization_job_id": job_id,
            "session_date": session_date,
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "last_updated": now_timestamp,
            "source": "full_session_recording",
        }).execute()

        logging.log_api_response(session_id=session_id,
                                endpoint_name=endpoints.DIARIZATION_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_POST)

        return {"job_id": job_id}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.DIARIZATION_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_POST)
        raise HTTPException(status_code=status_code, detail=description)

"""
Meant to be used as a webhook so Speechmatics can notify us when a diarization operation is ready.

Arguments:
request – the incoming request.
"""
@app.post(endpoints.DIARIZATION_NOTIFICATION_ENDPOINT)
async def consume_notification(request: Request):
    try:
        authorization = request.headers["authorization"].split()[-1]
        if not security.access_token_is_valid(authorization):
            raise TOKEN_EXPIRED_ERROR
    except:
        raise TOKEN_EXPIRED_ERROR

    try:
        status_code = request.query_params["status"]
        id = request.query_params["id"]
        assert status_code.lower() == "success", f"Diarization failed for job ID {id}"

        supabase_client = library_clients.supabase_admin_instance()

        raw_data = await request.json()
        json_data = json.loads(json.dumps(raw_data))
        job_id = json_data["job"]["id"]
        summary = json_data["summary"]["content"]
        diarization = DiarizationCleaner().clean_transcription(json_data["results"])

        now_timestamp = datetime.now().strftime(utilities.DATE_TIME_FORMAT)
        supabase_client.table('session_reports').update({
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

# Security endpoints

"""
Returns an oauth token to be used for invoking the endpoints.

Arguments:
form_data  – the data required to validate the user.
response – The response object to be used for creating the final response.
session_id  – the id of the current user session.
"""
@app.post(endpoints.TOKEN_ENDPOINT)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response,
    session_id: Annotated[Union[str, None], Cookie()] = None,
) -> security.Token:
    user = security.authenticate_user(security.users_db, form_data.username, form_data.password)
    session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=user,
                                                                                     response=response,
                                                                                     session_id=session_id)
    new_session_id = session_refresh_data._session_id
    logging.log_api_response(session_id=new_session_id,
                             endpoint_name=endpoints.TOKEN_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=endpoints.API_METHOD_POST,
                             description=f"Refreshing token from {session_id} to {new_session_id}")

    return session_refresh_data._auth_token

"""
Signs up a new user.

Arguments:
signup_data – the data to be used to sign up the user.
response – the response model to be used for creating the final response.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.SIGN_UP_ENDPOINT)
async def sign_up(signup_data: models.SignupData,
                  response: Response,
                  authorization: Annotated[Union[str, None], Cookie()] = None,
                  current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            endpoint_name=endpoints.SIGN_UP_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        supabase_client: Client = library_clients.supabase_admin_instance()
        res = supabase_client.auth.sign_up({
            "email": signup_data.user_email,
            "password": signup_data.user_password,
        })

        json_response = json.loads(res.json())
        assert (json_response["user"]["role"] == 'authenticated'
            and json_response["session"]["access_token"]
            and json_response["session"]["refresh_token"]), "Something went wrong when signing up the user"

        user_id = json_response["user"]["id"]
        supabase_client.table('therapists').insert({
            "id": user_id,
            "first_name": signup_data.first_name,
            "middle_name": signup_data.middle_name,
            "last_name": signup_data.last_name,
            "birth_date": signup_data.birth_date,
            "login_mechanism": signup_data.signup_mechanism,
            "email": signup_data.user_email,
            "language_preference": signup_data.language_preference,
        }).execute()

        logging.log_api_response(therapist_id=user_id,
                                session_id=session_id,
                                endpoint_name=endpoints.SIGN_UP_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=endpoints.API_METHOD_POST)

        return {
            "user_id": user_id,
            "access_token": json_response["session"]["access_token"],
            "refresh_token": json_response["session"]["refresh_token"]
        }
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.SIGN_UP_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=endpoints.API_METHOD_POST)
        raise HTTPException(status_code=status_code,
                            detail=description)

"""
Logs out the user.

Arguments:
response – the object to be used for constructing the final response.
therapist_id – The therapist id associated with the operation.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.LOGOUT_ENDPOINT)
async def logout(response: Response,
                 therapist_id: Annotated[str, Form()],
                 authorization: Annotated[Union[str, None], Cookie()] = None,
                 current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: models.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            therapist_id=therapist_id,
                            method=endpoints.API_METHOD_POST,
                            endpoint_name=endpoints.LOGOUT_ENDPOINT,
                            auth_entity=current_user.username)

    response.delete_cookie("authorization")
    response.delete_cookie("session_id")

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             endpoint_name=endpoints.LOGOUT_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=endpoints.API_METHOD_POST)

    return {}
