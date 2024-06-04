import asyncio, base64, datetime, httpx, json, os, requests, shutil

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
from httpx import HTTPStatusError
from langcodes import Language
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient
from supabase import create_client, Client
from typing import Annotated, Union
from PIL import Image

from .assistant import query as query_handler
from .assistant import vector_writer
from .internal import models
from .internal import security

TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

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

# RAG Assistant endpoints

"""
Digests a new session report by:
1) Uploading the full text to Supabase
2) Uploading the vector embeddings to Pinecone
Returns a boolean value representing success.

Arguments:
session_report – the report associated with the new session.
authorization – The authorization cookie, if exists.
"""
@app.post("/v1/sessions")
def upload_new_session(session_report: models.SessionReport,
                       authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        supabase = supabase_instance(session_report.supabase_access_token,
                                    session_report.supabase_refresh_token)

        # Write full text to supabase
        supabase.table('session_reports').insert({
            "notes_text": session_report.text,
            "session_transcription": None,
            "session_date": session_report.date,
            "patient_id": session_report.patient_id,
            "therapist_id": session_report.therapist_id}).execute()
    except HTTPException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid tokens.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="The requested operation cannot be executed.")

    # Upload vector embeddings
    vector_writer.upload_session_vector(session_report.patient_id,
                                        session_report.text,
                                        session_report.date)

    return {}

"""
Executes a query to our RAG system.
Returns the query response.

Arguments:
query – the query that will be executed.
authorization – The authorization cookie, if exists.
"""
@app.post("/v1/assistant-queries")
def execute_assistant_query(query: models.AssistantQuery,
                            authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        if not Language.get(query.response_language_code).is_valid():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid response language code.")
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Check the language code you are sending.")

    # Confirm that the incoming patient id belongs to the incoming therapist id.
    # We do this to avoid surfacing information to the wrong therapist
    try:
        supabase = supabase_instance(query.supabase_access_token,
                                     query.supabase_refresh_token)
        patient_therapist_check = supabase.from_('patients').select('*').eq('therapist_id',
                                                                            query.therapist_id).eq('id',
                                                                                                   query.patient_id).execute()
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid access and/or refresh tokens.")

    if len(patient_therapist_check.data) == 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="There isn't a match between that patient and therapist.")

    # Go through with the query
    response = query_handler.query_store(query.patient_id,
                                         query.text,
                                         query.response_language_code)

    if response.reason is query_handler.QueryStoreResultReason.INDEX_DOES_NOT_EXIST:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Store does not exist for this patient.")
    elif response.reason is query_handler.QueryStoreResultReason.UNKNOWN_FAILURE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    assert response.reason is query_handler.QueryStoreResultReason.SUCCESS

    return {"response": response.response_token}

"""
Returns a new greeting to the user.

Arguments:
greeting – the greeting parameters to be used.
authorization – The authorization cookie, if exists.
"""
@app.post("/v1/greetings")
def fetch_greeting(greeting_params: models.AssistantGreeting,
                   authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    try:
        if not Language.get(greeting_params.response_language_code).is_valid():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid response language code.")
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Check the language code you are sending.")
    return {"message": query_handler.create_greeting(greeting_params.addressing_name,
                                                     greeting_params.response_language_code)}

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
"""
@app.post("/v1/image-files")
def upload_session_notes_image(image: UploadFile = File(...),
                               authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    url = os.getenv("DOCUPANDA_URL")
    api_key = os.getenv("DOCUPANDA_API_KEY")
    file_name, file_extension = os.path.splitext(image.filename)

    # Format name to be used for image copy using current timestamp
    files_dir = 'app/files'
    pdf_extension = '.pdf'
    image_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    image_copy_path = files_dir + '/' + image_copy_bare_name + file_extension
    image_copy_pdf_path = files_dir + '/' + image_copy_bare_name + pdf_extension
    files_to_clean = [image_copy_path]

    # Write incoming image to our local volume for further processing
    with open(image_copy_path, 'wb+') as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Convert to PDF if necessary
    if file_extension.lower() != pdf_extension:
        Image.open(image_copy_path).convert('RGB').save(image_copy_pdf_path)
        files_to_clean.append(image_copy_pdf_path)

    if not os.path.exists(image_copy_pdf_path):
        os.remove(image_copy_path)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Something went wrong while processing the image.")
    
    # Send to DocuPanda
    payload = {"document": {"file": {
        "contents": base64.b64encode(open(image_copy_pdf_path, 'rb').read()).decode(),
        "filename": file_name + pdf_extension
    }}}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-API-Key": api_key
    }

    response = requests.post(url, json=payload, headers=headers)

    # Clean up temp files
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(clean_up_files(files_to_clean))

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Something went wrong while uploading the image.")

    document_id = response.json()['documentId']
    return {"document_id": document_id}

"""
Returns the text extracted from the incoming document_id.

Arguments:
document_id – the id of the document to be textracted.
authorization – The authorization cookie, if exists.
"""
@app.get("/v1/text-extractions")
def extract_text(document_id: str = None,
                 authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    if document_id == None or document_id == "":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Didn't receive a valid document id.")

    url = os.getenv("DOCUPANDA_URL") + "/" + document_id

    headers = {
        "accept": "application/json",
        "X-API-Key": os.getenv("DOCUPANDA_API_KEY")
    }

    response = requests.get(url, headers=headers)
    
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Something went wrong when extracting the text.")

    text_sections = response.json()['result']['pages'][0]['sections']
    full_text = ""
    for section in text_sections:
        full_text = full_text + section['text'] + " "

    return {"extraction": full_text}

# Audio handling endpoint

"""
Returns the transcription created from the incoming audio file.

Arguments:
audio_file – the audio file for which the transcription will be created.
authorization – The authorization cookie, if exists.
"""
@app.post("/v1/notes-transcriptions")
async def transcribe_notes(audio_file: UploadFile = File(...),
                                authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    _, file_extension = os.path.splitext(audio_file.filename)
    files_dir = 'app/files'
    audio_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

    try:
        # Write incoming audio to our local volume for further processing
        with open(audio_copy_path, 'wb+') as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        if not os.path.exists(audio_copy_path):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Something went wrong while processing the file.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, 
                            detail="Something went wrong while uploading the file.")
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
                                                                      timeout=httpx.Timeout(300.0, connect=10.0))

        json_response = json.loads(response.to_json(indent=4))
        transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="The transcription operation failed.")
    finally:
        await clean_up_files([audio_copy_path])

    return {"transcript": transcript}

"""
Returns the transcription created from the incoming audio file.
Meant to be used for diarizing sessions.

Arguments:
audio_file – the audio file for which the diarized transcription will be created.
authorization – The authorization cookie, if exists.
"""
@app.post("/v1/session-transcriptions")
async def transcribe_session(audio_file: UploadFile = File(...),
                             authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    _, file_extension = os.path.splitext(audio_file.filename)
    files_dir = 'app/files'
    audio_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

    try:
        # Write incoming audio to our local volume for further processing
        with open(audio_copy_path, 'wb+') as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        if not os.path.exists(audio_copy_path):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Something went wrong while processing the file.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Something went wrong while uploading the file.")
    finally:
        await audio_file.close()

    # Process local copy with Speechmatics client
    settings = ConnectionSettings(
        url=os.getenv("SPEECHMATICS_URL"),
        auth_token=os.getenv("SPEECHMATICS_API_KEY"),
    )

    conf = {
        "type": "transcription",
        "transcription_config": {
            "language": "auto",
            "diarization": "speaker",
            "enable_entities": True,
        },
        "language_identification_config": {
            "expected_languages": ["en", "es"],
            "low_confidence_action": "allow"
        },
        "summarization_config": {
            "content_type": "conversational",
            "summary_length": "detailed",
            "summary_type": "bullets"
        }
    }

    with BatchClient(settings) as client:
        try:
            job_id = client.submit_job(
                audio=audio_copy_path,
                transcription_config=conf,
            )

            # Note that in production, you should set up notifications instead of polling.
            # Notifications are described here: https://docs.speechmatics.com/features-other/notifications
            transcript = client.wait_for_completion(job_id, transcription_format="json-v2")
            summary = transcript["summary"]["content"]
            return {"transcription_id": "<to-be-implemented>", "summary": summary}
        except TimeoutError as e:
            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="The transcription operation failed.")
        finally:
            await clean_up_files([audio_copy_path])

# Security endpoints

"""
Returns an oauth token to be used for invoking the endpoints.

Arguments:
form_data  – the data required to validate the user.
response – The response object to be used for creating the final response.
"""
@app.post("/token")
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
    return security.Token(access_token=access_token, token_type="bearer")

@app.post("/logout")
async def logout(response: Response,
                 authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise TOKEN_EXPIRED_ERROR

    response.delete_cookie("authorization")
    return {}

# Helper functions

"""
Cleans up the incoming set of files from the local directory.

Arguments:
files  – the set of files to be cleaned up
"""
async def clean_up_files(files):
    for file in files:
        os.remove(file)

"""
Returns an active supabase instance.

Arguments:
access_token  – the access_token associated with a live supabase session
refresh_token  – the refresh_token associated with a live supabase session
"""
def supabase_instance(access_token, refresh_token) -> Client:
    key: str = os.environ.get("SUPABASE_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    
    try:
        supabase: Client = create_client(url, key)
        supabase.auth.set_session(access_token=access_token,
                                refresh_token=refresh_token)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="The incoming tokens are invalid.")

    return supabase
