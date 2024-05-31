import asyncio, base64, datetime, httpx, json, os, requests, shutil

import gotrue.errors
import postgrest.exceptions
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import (
    Depends,
    HTTPException,
    FastAPI,
    File,
    status,
    UploadFile)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from langcodes import Language
from supabase import create_client, Client
from typing import Annotated
from PIL import Image

import query as query_handler
import vector_writer
from models import (AssistantGreeting,
                    AssistantQuery,
                    SessionReport) 
from security import (ACCESS_TOKEN_EXPIRE_MINUTES,
                      Token,
                      authenticate_user,
                      create_access_token,
                      users_db,
                      oauth2_scheme)

app = FastAPI()

origins = [
    # Daniel Daza development
    "http://localhost:5173",
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
_  – oauth2 token
session_report – the report associated with the new session
"""
@app.post("/v1/sessions")
def upload_new_session(_: Annotated[str, Depends(oauth2_scheme)],
                       session_report: SessionReport):
    try:
        supabase = supabase_instance(session_report.supabase_access_token,
                                    session_report.supabase_refresh_token)

        # Write full text to supabase
        supabase.table('session_reports').insert({
            "session_text": session_report.text,
            "session_date": session_report.date,
            "patient_id": session_report.patient_id,
            "therapist_id": session_report.therapist_id}).execute()
    except gotrue.errors.AuthApiError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid access and/or refresh tokens.")
    except:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                            detail="The attempted operation was not accepted.")

    # Upload vector embeddings
    vector_writer.upload_session_vector(session_report.patient_id,
                                        session_report.text,
                                        session_report.date)

    return {}

"""
Executes a query to our RAG system.
Returns the query response.

Arguments:
_  – oauth2 token
query – the query that will be executed
"""
@app.post("/v1/assistant-queries")
def execute_assistant_query(_: Annotated[str, Depends(oauth2_scheme)],
                            query: AssistantQuery):
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
    except gotrue.errors.AuthApiError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid access and/or refresh tokens.")
    except:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                            detail="The attempted operation was not accepted.")

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
greeting – the greeting parameters to be used
_  – oauth2 token
"""
@app.post("/v1/greetings")
def fetch_greeting(greeting_params: AssistantGreeting, _: Annotated[str, Depends(oauth2_scheme)]):
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
_  – oauth2 token
"""
@app.get("/v1/healthcheck")
def read_healthcheck(_: Annotated[str, Depends(oauth2_scheme)]):
     return {"status": "ok"}

# Image handling endpoints

"""
Returns a document_id value associated with the file that was uploaded.

Arguments:
_  – oauth2 token
image – the image to be uploaded
"""
@app.post("/v1/image-files")
def upload_session_notes_image(_: Annotated[str, Depends(oauth2_scheme)],
                               image: UploadFile = File(...)):
    url = os.getenv("DOCUPANDA_URL")
    api_key = os.getenv("DOCUPANDA_API_KEY")
    file_name, file_extension = os.path.splitext(image.filename)

    # Format name to be used for image copy using current timestamp
    files_dir = 'files'
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
_  – oauth2 token
document_id – the id of the document to be textracted
"""
@app.get("/v1/text-extractions")
def extract_text(_: Annotated[str, Depends(oauth2_scheme)],
                 document_id: str = None):
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
_  – oauth2 token
audio_file – the audio file for which the transcription will be created
"""
@app.post("/v1/audio-transcriptions")
async def transcribe_audio_file(_: Annotated[str, Depends(oauth2_scheme)],
                                audio_file: UploadFile = File(...)):
    _, file_extension = os.path.splitext(audio_file.filename)
    files_dir = 'files'
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

    clean_up_files([audio_copy_path])
    return {"transcript": transcript}

# Security endpoints

"""
Returns an oauth token to be used for invoking the endpoints.

Arguments:
form_data  – the data required to validate the user
"""
@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

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
    
    supabase: Client = create_client(url, key)
    supabase.auth.set_session(access_token=access_token,
                              refresh_token=refresh_token)
    return supabase
