import asyncio, base64, datetime, os, requests, shutil
from datetime import timedelta

from fastapi import Depends, HTTPException, FastAPI, File, status, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
import gotrue.errors
import postgrest.exceptions
from pydantic import BaseModel
import query as query_handler
from security import ACCESS_TOKEN_EXPIRE_MINUTES, User, Token, authenticate_user, create_access_token, get_current_active_user, users_db
from supabase import create_client, Client
from typing import Annotated
from PIL import Image
import vector_writer as vector_writer

class SessionReport(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    date: str
    therapist_username: str
    therapist_password: str

class AssistantQuery(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    therapist_username: str
    therapist_password: str
    
class Patient(BaseModel):
    id: str

class ImageItem(BaseModel):
    document_id: str

app = FastAPI()

@app.post("/v1/sessions")
def upload_new_session(session_report: SessionReport):
    try:
        supabase = supabase_instance(session_report.therapist_username,
                                    session_report.therapist_password)
    except gotrue.errors.AuthApiError as e:
        error_message = "Something went wrong when authenticating user"
        if e.status == 400:
            error_message = "Wrong therapist credentials"
        return {"success": False, "error": error_message}
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

@app.get("/v1/assistant-queries")
def execute_assistant_query(query: AssistantQuery):
    try:
        supabase = supabase_instance(query.therapist_username,
                                    query.therapist_password)
    except gotrue.errors.AuthApiError as e:
        error_message = "Something went wrong when authenticating user"
        if e.status == 400:
            error_message = "Wrong therapist credentials"
        return {"success": False, "error": error_message}

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

    response = query_handler.query_store(query.patient_id, query.text)
    return {"success": True if response.reason == query_handler.QueryStoreResultReason.SUCCESS else False,
            "response": response.response_token}

@app.get("/v1/greetings")
def fetch_greeting():
    return {"success": True, "message": query_handler.create_greeting()}

@app.get("/v1/healthcheck")
def read_healthcheck():
     return {"status": "ok"}

@app.post("/v1/image-files")
def upload_session_notes_image(image: UploadFile = File(...)):
    url = os.getenv("DOCUPANDA_URL")
    api_key = os.getenv("DOCUPANDA_API_KEY")
    file_name, file_extension = os.path.splitext(image.filename)

    # Format name to be used for image copy using current timestamp
    image_data_dir = 'image-data'
    pdf_extension = '.pdf'
    image_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    image_copy_path = image_data_dir + '/' + image_copy_bare_name + file_extension
    image_copy_pdf_path = image_data_dir + '/' + image_copy_bare_name + pdf_extension
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
    loop.run_until_complete(clean_up_images(files_to_clean))

    if response.status_code != 200:
        return {"success": False,
            "message": f"Something went wrong when uploading the image"}

    document_id = response.json()['documentId']
    return {"success": True,
            "document_id": document_id}

@app.get("/v1/text-extractions")
def extract_text(image_item: ImageItem):
    url = os.getenv("DOCUPANDA_URL") + "/" + image_item.document_id

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


@app.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user

@app.get("/users/me/items/")
async def read_own_items(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return [{"item_id": "Foo", "owner": current_user.username}]

# Private funtions 

async def clean_up_images(images):
    for image in images:
        os.remove(image)

def supabase_instance(username, password) -> Client:
    key: str = os.environ.get("SUPABASE_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    
    supabase: Client = create_client(url, key)
    supabase.auth.sign_in_with_password({"email": username, "password": password})

    return supabase
