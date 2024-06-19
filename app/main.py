import json, uuid

from datetime import datetime, timedelta
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

DATE_TIME_TIMESTAMP = "%m-%d-%Y %H:%M:%S"

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
session_notes – the report associated with the new session.
response – the response model with which to create the final response.
authorization – the authorization cookie, if exists.
session_id – the session_id cookie, if exists.
"""
@app.post(endpoints.SESSION_UPLOAD_ENDPOINT)
async def insert_new_session(session_report: models.SessionNotesInsert,
                             response: Response,
                             authorization: Annotated[Union[str, None], Cookie()] = None,
                             session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            patient_id=session_report.patient_id,
                            therapist_id=session_report.therapist_id,
                            endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                            method=endpoints.API_METHOD_POST,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    try:
        supabase_client = library_clients.supabase_user_instance(session_report.supabase_access_token,
                                                                 session_report.supabase_refresh_token)
        now_timestamp = datetime.now().strftime(DATE_TIME_TIMESTAMP)
        supabase_client.table('session_reports').insert({
            "notes_text": session_report.text,
            "session_date": session_report.date,
            "patient_id": session_report.patient_id,
            "source": session_report.source,
            "last_updated": now_timestamp,
            "therapist_id": session_report.therapist_id}).execute()

        # Upload vector embeddings
        vector_writer.insert_session_vector(session_report.patient_id,
                                            session_report.text,
                                            session_report.date)
    except HTTPException as e:
        status_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          therapist_id=session_report.therapist_id,
                          patient_id=session_report.patient_id,
                          endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        logging.log_error(session_id=session_id,
                          therapist_id=session_report.therapist_id,
                          patient_id=session_report.patient_id,
                          endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=session_report.therapist_id,
                             patient_id=session_report.patient_id,
                             endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             description=None)

    return {}

"""
Updates a session report.

Arguments:
session_notes – the report associated with the new session.
response – the response model with which to create the final response.
authorization – the authorization cookie, if exists.
session_id – the session_id cookie, if exists.
"""
@app.put(endpoints.SESSION_UPLOAD_ENDPOINT)
async def update_session(session_notes: models.SessionNotesUpdate,
                         response: Response,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            patient_id=session_notes.patient_id,
                            therapist_id=session_notes.therapist_id,
                            endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                            method=endpoints.API_METHOD_PUT,
                            auth_entity=(await (security.get_current_user(authorization))).username,
                            description=f"Updated session with id {session_notes.session_notes_id}")

    try:
        supabase_client = library_clients.supabase_user_instance(session_notes.supabase_access_token,
                                                                 session_notes.supabase_refresh_token)

        now_timestamp = datetime.now().strftime(DATE_TIME_TIMESTAMP)
        supabase_client.table('session_reports').update({
            "notes_text": session_notes.text,
            "session_date": session_notes.date,
            "last_updated": now_timestamp,
            "session_diarization": session_notes.diarization,
        }).eq('id', session_notes.session_notes_id).execute()

        # Upload vector embeddings
        vector_writer.update_session_vector(session_notes.patient_id,
                                            session_notes.text,
                                            session_notes.date)
    except HTTPException as e:
        status_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          therapist_id=session_notes.therapist_id,
                          patient_id=session_notes.patient_id,
                          endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        logging.log_error(session_id=session_id,
                          therapist_id=session_notes.therapist_id,
                          patient_id=session_notes.patient_id,
                          endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=session_notes.therapist_id,
                             patient_id=session_notes.patient_id,
                             endpoint_name=endpoints.SESSION_UPLOAD_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             description=None)

    return {}

"""
Executes a query to our assistant system.
Returns the query response.

Arguments:
query – the query that will be executed.
response – the response model with which to create the final response.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.QUERIES_ENDPOINT)
async def execute_assistant_query(query: models.AssistantQuery,
                                  response: Response,
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            therapist_id=query.therapist_id,
                            patient_id=query.patient_id,
                            endpoint_name=endpoints.QUERIES_ENDPOINT,
                            method=endpoints.API_METHOD_POST,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    # Confirm that the incoming patient id belongs to the incoming therapist id.
    # We do this to avoid surfacing information to the wrong therapist
    try:
        assert Language.get(query.response_language_code).is_valid(), "Invalid response_language_code parameter"
        supabase_client = library_clients.supabase_user_instance(query.supabase_access_token,
                                                                 query.supabase_refresh_token)
        user_response = json.loads(supabase_client.auth.get_user().json())
        therapist_id = user_response["user"]["id"]

        patient_therapist_match = (0 != len(
            (supabase_client.from_('patients').select('*').eq('therapist_id', therapist_id).eq('id',
                                                                                                    query.patient_id).execute()
        ).data))
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        logging.log_error(session_id=session_id,
                          patient_id=query.patient_id,
                          endpoint_name=endpoints.QUERIES_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    if not patient_therapist_match:
        description = "There isn't a patient-therapist match with the incoming ids."
        status_code = status.HTTP_403_FORBIDDEN
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=query.patient_id,
                          endpoint_name=endpoints.QUERIES_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    # Go through with the query
    response = query_handler.query_store(index_id=query.patient_id,
                                         input=query.text,
                                         response_language_code=query.response_language_code,
                                         querying_user=therapist_id,
                                         session_id=session_id,
                                         endpoint_name=endpoints.QUERIES_ENDPOINT,
                                         method=endpoints.API_METHOD_POST)

    if response.status_code != status.HTTP_200_OK:
        description = "Something failed when trying to execute the query"
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=query.patient_id,
                          endpoint_name=endpoints.QUERIES_ENDPOINT,
                          error_code=response.status_code,
                          description=description)
        raise HTTPException(status_code=response.status_code,
                            detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             patient_id=query.patient_id,
                             endpoint_name=endpoints.QUERIES_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             description=None)

    return {"response": response.response_token}

"""
Returns a new greeting to the user.

Arguments:
response – the response model used for the final response that will be returned.
addressing_name – the name to be used for addressing the user in the greeting.
response_language_code – the language code to be used for creating the greeting.
client_tz_identifier – the timezone identifier used to fetch the client's weekday.
therapist_id – the id of the therapist for which the greeting is being created.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.GREETINGS_ENDPOINT)
async def fetch_greeting(response: Response,
                         addressing_name: Annotated[str, Form()],
                         response_language_code: Annotated[str, Form()],
                         client_tz_identifier: Annotated[str, Form()],
                         therapist_id: Annotated[str, Form()],
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            therapist_id=therapist_id,
                            endpoint_name=endpoints.GREETINGS_ENDPOINT,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    try:
        assert Language.get(response_language_code).is_valid(), "Invalid response_language_code parameter"
        result = query_handler.create_greeting(name=addressing_name,
                                               language_code=response_language_code,
                                               tz_identifier=client_tz_identifier,
                                               session_id=session_id,
                                               endpoint_name=endpoints.GREETINGS_ENDPOINT,
                                               therapist_id=therapist_id,
                                               method=endpoints.API_METHOD_POST)
    except Exception as e:
        status_code = status.HTTP_400_BAD_REQUEST
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.GREETINGS_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    log_description = ''.join(['language_code:',
                           response_language_code,
                           'tz_identifier:',
                           client_tz_identifier])
    logging.log_api_response(session_id=session_id,
                             endpoint_name=endpoints.GREETINGS_ENDPOINT,
                             therapist_id=therapist_id,
                             http_status_code=status.HTTP_200_OK,
                             description=log_description)

    if result.status_code is not status.HTTP_200_OK:
        raise HTTPException(status_code=result.status_code,
                            detail=result.response_token)

    return {"message": result.response_token}

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
session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.IMAGE_UPLOAD_ENDPOINT)
async def upload_session_notes_image(response: Response,
                                     patient_id: Annotated[str, Form()],
                                     therapist_id: Annotated[str, Form()],
                                     image: UploadFile = File(...),
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            patient_id=patient_id,
                            therapist_id=therapist_id,
                            endpoint_name=endpoints.IMAGE_UPLOAD_ENDPOINT,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    try:
        document_id = await library_clients.upload_image_for_textraction(image)
    except HTTPException as e:
        status_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.IMAGE_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)
    except Exception as e:
        status_code = status.HTTP_409_CONFLICT
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.IMAGE_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             patient_id=patient_id,
                             endpoint_name=endpoints.IMAGE_UPLOAD_ENDPOINT,
                             http_status_code=status.HTTP_200_OK)

    return {"document_id": document_id}

"""
Returns the text extracted from the incoming document_id.

Arguments:
response – the response model to be used for crafting the final response.
therapist_id – the therapist_id for the operation.
patient_id – the patient_id for the operation.
document_id – the id of the document to be textracted.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.get(endpoints.TEXT_EXTRACTION_ENDPOINT)
async def extract_text(response: Response,
                       therapist_id: Annotated[str, Form()],
                       patient_id: Annotated[str, Form()],
                       document_id: str = None,
                       authorization: Annotated[Union[str, None], Cookie()] = None,
                       session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_GET,
                            therapist_id=therapist_id,
                            patient_id=patient_id,
                            endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    if document_id == None or document_id == "":
        description = "Didn't receive a valid document id."
        status_code = status.HTTP_409_CONFLICT
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=patient_id,
                          endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    try:
        full_text = library_clients.extract_text(document_id)
    except HTTPException as e:
        status_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=patient_id,
                          endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)
    except Exception as e:
        status_code = status.HTTP_409_CONFLICT
        description = str(e)
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=patient_id,
                          endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             patient_id=patient_id,
                             endpoint_name=endpoints.TEXT_EXTRACTION_ENDPOINT,
                             http_status_code=status.HTTP_200_OK)

    return {"extraction": full_text}

# Audio handling endpoint

"""
Returns the transcription created from the incoming audio file.

Arguments:
response – the response model with which to create the final response.
therapist_id – the id of the therapist associated with the session notes.
patient_id – the id of the patient associated with the session notes.
audio_file – the audio file for which the transcription will be created.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.NOTES_TRANSCRIPTION_ENDPOINT)
async def transcribe_session_notes(response: Response,
                                   therapist_id: Annotated[str, Form()],
                                   patient_id: Annotated[str, Form()],
                                   audio_file: UploadFile = File(...),
                                   authorization: Annotated[Union[str, None], Cookie()] = None,
                                   session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            therapist_id=therapist_id,
                            patient_id=patient_id,
                            endpoint_name=endpoints.NOTES_TRANSCRIPTION_ENDPOINT,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    try:
        transcript = await library_clients.transcribe_audio_file(audio_file)
    except Exception as e:
        status_code = status.HTTP_409_CONFLICT
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.NOTES_TRANSCRIPTION_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             patient_id=patient_id,
                             endpoint_name=endpoints.NOTES_TRANSCRIPTION_ENDPOINT,
                             http_status_code=status.HTTP_200_OK)

    return {"transcript": transcript}

"""
Returns the transcription created from the incoming audio file.
Meant to be used for diarizing sessions.

Arguments:
response – the response model with which to create the final response.
therapist_id – the id of the therapist associated with the session notes.
patient_id – the id of the patient associated with the session notes.
audio_file – the audio file for which the diarized transcription will be created.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.DIARIZATION_ENDPOINT)
async def diarize_session(response: Response,
                          session_date: Annotated[str, Form()],
                          therapist_id: Annotated[str, Form()],
                          patient_id: Annotated[str, Form()],
                          audio_file: UploadFile = File(...),
                          authorization: Annotated[Union[str, None], Cookie()] = None,
                          session_id: Annotated[Union[str, None], Cookie()] = None,):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            patient_id=patient_id,
                            therapist_id=therapist_id,
                            method=endpoints.API_METHOD_POST,
                            endpoint_name=endpoints.DIARIZATION_ENDPOINT,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    try:
        assert utilities.is_valid_date(session_date), "Invalid date. The expected format is mm/dd/yyyy"

        supabase_client = library_clients.supabase_admin_instance()
        job_id: str = await library_clients.diarize_audio_file(auth_token=authorization,
                                                               audio_file=audio_file)

        now_timestamp = datetime.now().strftime(DATE_TIME_TIMESTAMP)
        supabase_client.table('session_reports').insert({
            "session_diarization_job_id": job_id,
            "session_date": session_date,
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "last_updated": now_timestamp,
            "source": "full_session_recording",
        }).execute()
    except HTTPException as e:
        resulting_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.DIARIZATION_ENDPOINT,
                          error_code=resulting_code,
                          description=description)
        raise HTTPException(status_code=resulting_code, detail=description)
    except Exception as e:
        resulting_code = status.HTTP_409_CONFLICT
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.DIARIZATION_ENDPOINT,
                          error_code=resulting_code,
                          description=description)
        raise HTTPException(status_code=resulting_code, detail=description)

    logging.log_api_response(session_id=session_id,
                             endpoint_name=endpoints.DIARIZATION_ENDPOINT,
                             http_status_code=status.HTTP_200_OK)

    return {"job_id": job_id}

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

        now_timestamp = datetime.now().strftime(DATE_TIME_TIMESTAMP)
        supabase_client.table('session_reports').update({
            "notes_text": summary,
            "session_diarization": diarization,
            "last_updated": now_timestamp,
        }).eq('session_diarization_job_id', job_id).execute()

    except HTTPException as e:
        description = str(e)
        logging.log_diarization_event(error_code=e.status_code, description=description)
        raise HTTPException(status_code=e.status_code, detail=description)
    except Exception as e:
        description = str(e)
        resulting_code = status.HTTP_417_EXPECTATION_FAILED
        logging.log_diarization_event(error_code=resulting_code, description=description)
        raise HTTPException(status_code=resulting_code, detail=description)

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
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    response.delete_cookie("authorization")
    response.set_cookie(key="authorization",
                        value=access_token,
                        httponly=True,
                        secure=True,
                        samesite="none")
    token = security.Token(access_token=access_token, token_type="bearer")

    new_session_id = uuid.uuid1()
    response.delete_cookie("session_id")
    response.set_cookie(key="session_id",
                    value=new_session_id,
                    httponly=True,
                    secure=True,
                    samesite="none")

    logging.log_api_response(session_id=new_session_id,
                             endpoint_name=endpoints.TOKEN_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             description=f"Refreshing token from {session_id} to {new_session_id}")

    return token

"""
Signs up a new user.

Arguments:
signup_data – the data to be used to sign up the user.
response – the response model to be used for creating the final response.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.SIGN_UP_ENDPOINT)
async def sign_up(signup_data: models.SignupData,
                  response: Response,
                  authorization: Annotated[Union[str, None], Cookie()] = None,
                  session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            method=endpoints.API_METHOD_POST,
                            endpoint_name=endpoints.SIGN_UP_ENDPOINT,
                            auth_entity=(await (security.get_current_user(authorization))).username)

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
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        logging.log_error(session_id=session_id,
                          endpoint_name=endpoints.SIGN_UP_ENDPOINT,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    logging.log_api_response(therapist_id=user_id,
                             session_id=session_id,
                             endpoint_name=endpoints.SIGN_UP_ENDPOINT,
                             http_status_code=status.HTTP_200_OK)

    return {
        "user_id": user_id,
        "access_token": json_response["session"]["access_token"],
        "refresh_token": json_response["session"]["refresh_token"]
    }

"""
Logs out the user.

Arguments:
response – the object to be used for constructing the final response.
therapist_id – The therapist id associated with the operation.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(endpoints.LOGOUT_ENDPOINT)
async def logout(response: Response,
                 therapist_id: Annotated[str, Form()],
                 authorization: Annotated[Union[str, None], Cookie()] = None,
                 session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id=session_id,
                            therapist_id=therapist_id,
                            method=endpoints.API_METHOD_POST,
                            endpoint_name=endpoints.LOGOUT_ENDPOINT,
                            auth_entity=(await (security.get_current_user(authorization))).username)

    response.delete_cookie("authorization")

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             endpoint_name=endpoints.LOGOUT_ENDPOINT,
                             http_status_code=status.HTTP_200_OK)

    session_id = None
    return {}

# Private methods

"""
Validates the incoming session_id cookie.

Arguments:
response – the response object where we can update cookies.
cookie – the cookie to be validated, if exists.
"""
def validate_session_id_cookie(response: Response,
                               session_id_cookie: Annotated[Union[str, None], Cookie()] = None) -> uuid.UUID | None:
    if session_id_cookie is not None:
        return session_id_cookie

    session_id = uuid.uuid1()
    response.set_cookie(key="session_id",
                value=session_id,
                httponly=True,
                secure=True,
                samesite="none")
    return session_id
