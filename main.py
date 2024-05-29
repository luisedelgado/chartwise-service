import asyncio, base64, datetime, httpx, json, os, requests, shutil
from datetime import timedelta
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import Depends, HTTPException, FastAPI, File, status, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import gotrue.errors
import postgrest.exceptions
from pydantic import BaseModel
import query as query_handler
from security import (ACCESS_TOKEN_EXPIRE_MINUTES,
                      Token,
                      authenticate_user,
                      create_access_token,
                      users_db,
                      oauth2_scheme)
from supabase import create_client, Client
from typing import Annotated
from PIL import Image
import vector_writer as vector_writer

class SessionReport(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    date: str
    supabase_access_token: str
    supabase_refresh_token: str

class AssistantQuery(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    supabase_access_token: str
    supabase_refresh_token: str

class AssistantGreeting(BaseModel):
    addressing_name: str
    language_code: str
    
class AudioItem(BaseModel):
    audio_file_url: str

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

@app.post("/v1/sessions")
def upload_new_session(token: Annotated[str, Depends(oauth2_scheme)],
                       session_report: SessionReport):
    try:
        supabase = supabase_instance(session_report.supabase_access_token,
                                    session_report.supabase_refresh_token)
    except gotrue.errors.AuthApiError as e:
        error_message = "Something is wrong with the payload you are sending"
        if e.status == 403:
            error_message = "There was an issue with the access and refresh tokens that were sent in"
        return {"success": False, "error": error_message}
    except:
        return {"success": False, "error": "Something is wrong with the payload you are sending"}
    
    try:
        # Write full text to supabase
        supabase.table('session_reports').insert({
            "session_text": session_report.text,
            "session_date": session_report.date,
            "patient_id": session_report.patient_id,
            "therapist_id": session_report.therapist_id}).execute()
    except postgrest.exceptions.APIError as e:
        error_message = "Something went wrong with the request"
        if e.code == '42501':
            error_message = "Request violated RLS policy"
        return {"success": False, "error": error_message}
    except:
        return {"success": False, "error": "Something went wrong with the request"}

    vector_writer.upload_session_vector(session_report.patient_id,
                                        session_report.text,
                                        session_report.date)

    return {"success": True}

@app.post("/v1/assistant-queries")
def execute_assistant_query(token: Annotated[str, Depends(oauth2_scheme)],
                            query: AssistantQuery):
    # Get supabase instance
    try:
        supabase = supabase_instance(query.supabase_access_token,
                                     query.supabase_refresh_token)
    except gotrue.errors.AuthApiError as e:
        error_message = "Something is wrong with the payload you are sending"
        if e.status == 403:
            error_message = "There was an issue with the access and refresh tokens that were sent in"
        return {"success": False, "error": error_message}
    except:
        return {"success": False, "error": "Something is wrong with the payload you are sending"}

    # Confirm that the incoming patient id is associated with the incoming therapist id
    try:
        res = supabase.from_('patients').select('*').eq('therapist_id',
                                                  query.therapist_id).eq('id',
                                                                         query.patient_id).execute()
        if len(res.data) == 0:
            return {"success": False, "error": "This patient/therapist combination does not match"}
    except postgrest.exceptions.APIError as e:
        error_message = "Something went wrong with the request"
        if e.code == '42501':
            error_message = "Request violated RLS policy"
        return {"success": False, "error": error_message}
    except:
        return {"success": False, "error": "Something went wrong with the request"}

    # Go through with the query
    response = query_handler.query_store(query.patient_id, query.text)
    return {"success": True if response.reason == query_handler.QueryStoreResultReason.SUCCESS else False,
            "response": response.response_token}

@app.post("/v1/greetings")
def fetch_greeting(greeting: AssistantGreeting, token: Annotated[str, Depends(oauth2_scheme)]):
    return {"success": True, "message": query_handler.create_greeting(greeting.addressing_name, greeting.language_code)}

@app.get("/v1/healthcheck")
def read_healthcheck(token: Annotated[str, Depends(oauth2_scheme)]):
     return {"status": "ok"}

@app.post("/v1/image-files")
def upload_session_notes_image(token: Annotated[str, Depends(oauth2_scheme)],
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
        return {"success": False,
            "message": f"There was an error while converting the image to PDF"}
    
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

    if response.status_code != 200:
        return {"success": False,
            "message": f"Something went wrong when uploading the image"}

    document_id = response.json()['documentId']
    return {"success": True,
            "document_id": document_id}

@app.get("/v1/text-extractions")
def extract_text(token: Annotated[str, Depends(oauth2_scheme)],
                 document_id: str = None):
    if document_id == None or document_id == "":
        return {"success": False,
            "message": f"Didn't receive a valid document id"}

    url = os.getenv("DOCUPANDA_URL") + "/" + document_id

    headers = {
        "accept": "application/json",
        "X-API-Key": os.getenv("DOCUPANDA_API_KEY")
    }

    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return {"success": False,
            "message": f"Something went wrong when extracting the text"}
    
    text_sections = response.json()['result']['pages'][0]['sections']
    full_text = ""
    for section in text_sections:
        full_text = full_text + section['text'] + " "

    return {"success": True, "extraction": full_text}

# Audio handling endpoint

@app.post("/v1/audio-transcriptions")
async def transcribe_audio_file(token: Annotated[str, Depends(oauth2_scheme)],
                                file: UploadFile = File(...)):
    file_name, file_extension = os.path.splitext(file.filename)
    files_dir = 'files'
    audio_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

    try:
        # Write incoming audio to our local volume for further processing
        with open(audio_copy_path, 'wb+') as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not os.path.exists(audio_copy_path):
            return {"success": False,
                "message": f"There was an error while manipulating the incoming file"}
    except Exception as e:
        print (e)
        return {"success":False,
                "message": "There was an error uploading the file"}
    finally:
        await file.close()
        
    try:
        # STEP 1 Create a Deepgram client using the API key
        deepgram = DeepgramClient(os.getenv("DG_API_KEY"))

        #STEP 2: Configure Deepgram options for audio analysis
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            detect_language=True,
            utterances=True,
            numerals=True
        )

        with open(audio_copy_path, "rb") as file:
            buffer_data = file.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        # STEP 3: Call the transcribe_file method with the text payload and options
        # this will increase the timeout to 300 seconds or 5 minutes
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload,
                                                                      options,
                                                                      timeout=httpx.Timeout(300.0, connect=10.0))

        # STEP 4: Extract the transcript and return it
        json_response = json.loads(response.to_json(indent=4))
        transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
    except TimeoutError as e:
        return {"success": False, "message": "The transcription operation timed out"}
    except Exception as e:
        return {"success": False, "message": e}

    clean_up_files([audio_copy_path])
    return {"success": True, "transcript": transcript}

# Security endpoints

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
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

# Private funtions 

async def clean_up_files(files):
    for file in files:
        os.remove(file)

def supabase_instance(access_token, refresh_token) -> Client:
    key: str = os.environ.get("SUPABASE_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    
    supabase: Client = create_client(url, key)
    supabase.auth.set_session(access_token=access_token,
                              refresh_token=refresh_token)
    return supabase
