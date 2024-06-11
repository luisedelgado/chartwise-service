import datetime, json, os, requests, shutil, ssl, uuid

from dataclasses import field
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import (
    Cookie,
    Depends,
    HTTPException,
    FastAPI,
    File,
    Response,
    status,
    UploadFile)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from httpx import Timeout
from langcodes import Language
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient
from supabase import Client
from typing import Annotated, Union

from .assistant import query as query_handler
from .assistant import vector_writer
from .data_processing import diarization_cleaner
from .internal import library_clients
from .internal import logging
from .internal import models
from .internal import security
from .internal import utilities

TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

# Keep sorted alphabetically
__assistant_queries_endpoint_name = "/v1/assistant-queries"
__greetings_endpoint_name = "/v1/greetings"
__image_files_endpoint_name = "/v1/image-files"
__logout_endpoint_name = "/logout"
__notes_transcriptions_endpoint_name = "/v1/notes-transcriptions"
__session_transcriptions_endpoint_name = "/v1/session-transcriptions"
__sessions_endpoint_name = "/v1/sessions"
__sign_up_endpoint_name = "/sign-up"
__text_extractions_endpoint_name = "/v1/text-extractions"
__token_endpoint_name = "/token"

app = FastAPI()

origins = [
    # Daniel Daza development
    "https://localhost:5173",
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
Digests a new session report by:
1) Uploading the full text to Supabase
2) Uploading the vector embeddings to Pinecone
Returns a boolean value representing success.

Arguments:
session_report – the report associated with the new session.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__sessions_endpoint_name)
def upload_new_session(session_report: models.SessionReport,
                       response: Response,
                       authorization: Annotated[Union[str, None], Cookie()] = None,
                       session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __sessions_endpoint_name)

    try:
        supabase_client = library_clients.supabase_user_instance(session_report.supabase_access_token,
                                                                 session_report.supabase_refresh_token)

        user_response = json.loads(supabase_client.auth.get_user().json())
        therapist_id = user_response["user"]["id"]

        # Write full text to supabase
        supabase_client.table('session_reports').insert({
            "notes_text": session_report.text,
            "session_transcription": None,
            "session_date": session_report.date,
            "patient_id": session_report.patient_id,
            "source": session_report.source,
            "therapist_id": therapist_id}).execute()

        # Upload vector embeddings
        vector_writer.upload_session_vector(session_report.patient_id,
                                            session_report.text,
                                            session_report.date)
    except HTTPException as e:
        status_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=session_report.patient_id,
                          endpoint_name=__sessions_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=session_report.patient_id,
                          endpoint_name=__sessions_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             patient_id=session_report.patient_id,
                             endpoint_name=__sessions_endpoint_name,
                             http_status_code=status.HTTP_200_OK,
                             description=None)

    return {}

"""
Executes a query to our RAG system.
Returns the query response.

Arguments:
query – the query that will be executed.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__assistant_queries_endpoint_name)
def execute_assistant_query(query: models.AssistantQuery,
                            response: Response,
                            authorization: Annotated[Union[str, None], Cookie()] = None,
                            session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __assistant_queries_endpoint_name)

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
                          endpoint_name=__assistant_queries_endpoint_name,
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
                          endpoint_name=__assistant_queries_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    # Go through with the query
    response = query_handler.query_store(query.patient_id,
                                         query.text,
                                         query.response_language_code)

    if response.status_code != status.HTTP_200_OK:
        description = "Something failed when trying to execute the query"
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=query.patient_id,
                          endpoint_name=__assistant_queries_endpoint_name,
                          error_code=response.status_code,
                          description=description)
        raise HTTPException(status_code=response.status_code,
                            detail=description)

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             patient_id=query.patient_id,
                             endpoint_name=__assistant_queries_endpoint_name,
                             http_status_code=200,
                             description=None)

    return {"response": response.response_token}

"""
Returns a new greeting to the user.

Arguments:
greeting – the greeting parameters to be used.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__greetings_endpoint_name)
def fetch_greeting(greeting_params: models.AssistantGreeting,
                   response: Response,
                   authorization: Annotated[Union[str, None], Cookie()] = None,
                   session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __greetings_endpoint_name)

    try:
        assert Language.get(greeting_params.response_language_code).is_valid(), "Invalid response_language_code parameter"
        result = query_handler.create_greeting(greeting_params.addressing_name,
                                               greeting_params.response_language_code,
                                               greeting_params.client_tz_identifier)
    except Exception as e:
        status_code = status.HTTP_400_BAD_REQUEST
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=__greetings_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    log_description = ''.join(['language_code:',
                           greeting_params.response_language_code,
                           'tz_identifier:',
                           greeting_params.client_tz_identifier])
    logging.log_api_response(session_id=session_id,
                             endpoint_name=__greetings_endpoint_name,
                             http_status_code=200,
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
@app.get("/v1/healthcheck")
def read_healthcheck(authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    return {"status": "ok"}

# Image handling endpoints

"""
Returns a document_id value associated with the file that was uploaded.

Arguments:
image – the image to be uploaded.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__image_files_endpoint_name)
def upload_session_notes_image(response: Response,
                               image: UploadFile = File(...),
                               authorization: Annotated[Union[str, None], Cookie()] = None,
                               session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __image_files_endpoint_name)

    try:
        document_id = library_clients.docupanda_upload_image(image)
    except HTTPException as e:
        status_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=__image_files_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)
    except Exception as e:
        status_code = status.HTTP_409_CONFLICT
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=__image_files_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)

    logging.log_api_response(session_id=session_id,
                             endpoint_name=__image_files_endpoint_name,
                             http_status_code=200)

    return {"document_id": document_id}

"""
Returns the text extracted from the incoming document_id.

Arguments:
document_id – the id of the document to be textracted.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.get(__text_extractions_endpoint_name)
def extract_text(response: Response,
                 document_id: str = None,
                 authorization: Annotated[Union[str, None], Cookie()] = None,
                 session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __text_extractions_endpoint_name)

    if document_id == None or document_id == "":
        description = "Didn't receive a valid document id."
        status_code = status.HTTP_409_CONFLICT
        logging.log_error(session_id=session_id,
                          endpoint_name=__text_extractions_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    try:
        full_text = library_clients.docupanda_extract_text(document_id)
    except HTTPException as e:
        status_code = e.status_code
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=__text_extractions_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)
    except Exception as e:
        status_code = status.HTTP_409_CONFLICT
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=__text_extractions_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code, detail=description)

    logging.log_api_response(session_id=session_id,
                             endpoint_name=__text_extractions_endpoint_name,
                             http_status_code=200)

    return {"extraction": full_text}

# Audio handling endpoint

"""
Returns the transcription created from the incoming audio file.

Arguments:
audio_file – the audio file for which the transcription will be created.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__notes_transcriptions_endpoint_name)
async def transcribe_notes(response: Response,
                           audio_file: UploadFile = File(...),
                           authorization: Annotated[Union[str, None], Cookie()] = None,
                           session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __notes_transcriptions_endpoint_name)

    _, file_extension = os.path.splitext(audio_file.filename)
    files_dir = 'app/files'
    audio_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

    try:
        # Write incoming audio to our local volume for further processing
        with open(audio_copy_path, 'wb+') as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        assert os.path.exists(audio_copy_path), "Something went wrong while processing the file."
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT
        logging.log_error(session_id=session_id,
                          endpoint_name=__notes_transcriptions_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)
    finally:
        await audio_file.close()

    # Process local copy with DeepgramClient
    try:
        deepgram = DeepgramClient(os.getenv("DG_API_KEY"))

        with open(audio_copy_path, "rb") as file:
            buffer_data = file.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            detect_language=True,
            utterances=True,
            numerals=True
        )

        # Increase the timeout to 300 seconds (5 minutes)
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload,
                                                                      options,
                                                                      timeout=Timeout(300.0, connect=10.0))

        json_response = json.loads(response.to_json(indent=4))
        transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
    except HTTPException as e:
        description = str(e)
        logging.log_error(session_id=session_id,
                          endpoint_name=__notes_transcriptions_endpoint_name,
                          error_code=e.status_code,
                          description=description)
        raise HTTPException(status_code=e.status_code,
                            detail=description)
    except Exception as e:
        description = "The transcription operation failed."
        status_code = status.HTTP_409_CONFLICT
        logging.log_error(session_id=session_id,
                          endpoint_name=__notes_transcriptions_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)
    finally:
        await utilities.clean_up_files([audio_copy_path])

    logging.log_api_response(session_id=session_id,
                             endpoint_name=__notes_transcriptions_endpoint_name,
                             http_status_code=200)

    return {"transcript": transcript}

"""
Returns the transcription created from the incoming audio file.
Meant to be used for diarizing sessions.

Arguments:
audio_file – the audio file for which the diarized transcription will be created.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__session_transcriptions_endpoint_name)
async def transcribe_session(response: Response,
                             audio_file: UploadFile = File(...),
                             authorization: Annotated[Union[str, None], Cookie()] = None,
                             session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __session_transcriptions_endpoint_name)

    # _, file_extension = os.path.splitext(audio_file.filename)
    # files_dir = 'app/files'
    # audio_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    # audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

    # try:
    #     # Write incoming audio to our local volume for further processing
    #     with open(audio_copy_path, 'wb+') as buffer:
    #         shutil.copyfileobj(audio_file.file, buffer)
    # 
    #     assert os.path.exists(audio_copy_path), "Something went wrong while processing the file."
    # except Exception as e:
    #     description = str(e)
    #     status_code = status.HTTP_409_CONFLICT
    #     logging.log_error(session_id=session_id,
    #                       endpoint_name=__session_transcriptions_endpoint_name,
    #                       error_code=status_code,
    #                       description=description)
    #     raise HTTPException(status_code=status_code,
    #                         detail=description)
    # finally:
    #     await audio_file.close()

    # # Temporary workaround until we add our own certificates
    # ssl_context = ssl._create_unverified_context()
    # #ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)

    # # Process local copy with Speechmatics client
    # settings = ConnectionSettings(
    #     url=os.getenv("SPEECHMATICS_URL"),
    #     auth_token=os.getenv("SPEECHMATICS_API_KEY"),
    #     ssl_context=ssl_context,
    # )

    # conf = {
    #     "type": "transcription",
    #     "transcription_config": {
    #         "language": "auto",
    #         "diarization": "speaker",
    #         "enable_entities": True,
    #     },
    #     "language_identification_config": {
    #         "expected_languages": ["en", "es"],
    #         "low_confidence_action": "allow"
    #     },
    #     "summarization_config": {
    #         "content_type": "conversational",
    #         "summary_length": "detailed",
    #         "summary_type": "bullets"
    #     }
    # }

    # with BatchClient(settings) as client:
    #     try:
    #         job_id = client.submit_job(
    #             audio=audio_copy_path,
    #             transcription_config=conf,
    #         )

    #         # Note that in production, you should set up notifications instead of polling.
    #         # Notifications are described here: https://docs.speechmatics.com/features-other/notifications
    #         transcript = client.wait_for_completion(job_id, transcription_format="json-v2")
    #         summary = transcript["summary"]["content"]
    #         return {"transcription_id": "", "summary": summary}
    #     except TimeoutError as e:
    #         status_code = status.HTTP_408_REQUEST_TIMEOUT
    #         logging.log_error(session_id=session_id,
    #                           endpoint_name=__session_transcriptions_endpoint_name,
    #                           error_code=status_code,
    #                           description=str(e))
    #         raise HTTPException(status_code=status_code)
    #     except Exception as e:
    #         status_code = status.HTTP_409_CONFLICT
    #         description = str(e)
    #         logging.log_error(session_id=session_id,
    #                           endpoint_name=__session_transcriptions_endpoint_name,
    #                           error_code=status_code,
    #                           description=description)
    #         raise HTTPException(status_code=status_code,
    #                             detail=description)
    #     finally:
    #         await utilities.clean_up_files([audio_copy_path])

    data = json.load(open('app/files/output.json'))
    summary = data["summary"]["content"]

    transcription_cleaner = diarization_cleaner.DiarizationCleaner()
    transcript = transcription_cleaner.clean_transcription(data["results"])

    logging.log_api_response(session_id=session_id,
                             endpoint_name=__session_transcriptions_endpoint_name,
                             http_status_code=200)

    return {"summary": summary, "transcription": transcript}

# Security endpoints

"""
Returns an oauth token to be used for invoking the endpoints.

Arguments:
form_data  – the data required to validate the user.
response – The response object to be used for creating the final response.
"""
@app.post(__token_endpoint_name)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response
) -> security.Token:
    user = security.authenticate_user(security.users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = datetime.timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    response.set_cookie(key="authorization",
                        value=access_token,
                        httponly=True,
                        secure=True,
                        samesite="none")
    token = security.Token(access_token=access_token, token_type="bearer")

    session_id = uuid.uuid1()
    response.set_cookie(key="session_id",
                    value=session_id,
                    httponly=True,
                    secure=True,
                    samesite="lax")

    logging.log_api_response(session_id=session_id,
                             endpoint_name=__token_endpoint_name,
                             http_status_code=200)

    return token

"""
Signs up a new user.

Arguments:
signup_data – the data to be used to sign up the user.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__sign_up_endpoint_name)
def sign_up(signup_data: models.SignupData,
            response: Response,
            authorization: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __sign_up_endpoint_name)

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
                          endpoint_name=__sign_up_endpoint_name,
                          error_code=status_code,
                          description=description)
        raise HTTPException(status_code=status_code,
                            detail=description)

    logging.log_api_response(therapist_id=user_id,
                             session_id=session_id,
                             endpoint_name=__sign_up_endpoint_name,
                             http_status_code=200)

    return {
        "user_id": user_id,
        "access_token": json_response["session"]["access_token"],
        "refresh_token": json_response["session"]["refresh_token"]
    }

"""
Logs out the user.

Arguments:
response – the object to be used for constructing the final response.
authorization – The authorization cookie, if exists.
session_id – The session_id cookie, if exists.
"""
@app.post(__logout_endpoint_name)
async def logout(response: Response,
                 authorization: Annotated[Union[str, None], Cookie()] = None,
                 session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    session_id = validate_session_id_cookie(response, session_id)
    logging.log_api_request(session_id, __logout_endpoint_name)

    response.delete_cookie("authorization")

    logging.log_api_response(session_id=session_id,
                             endpoint_name=__logout_endpoint_name,
                             http_status_code=200)

    session_id = None
    return {}

# Private methods

"""
Validates the incoming session_id cookie.

Arguments:
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
                samesite="lax")
    return session_id
