import asyncio, base64, datetime, os, requests, shutil, uuid
import query as query_handler
import vector_writer as vector_writer
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from supabase import create_client, Client
from PIL import Image

class SessionReport(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    date: str
    
class AssistantQuery(BaseModel):
    patient_id: str
    text: str
    
class Patient(BaseModel):
    id: str

class ImageItem(BaseModel):
    document_id: str

app = FastAPI()

@app.post("/v1/sessions")
def upload_new_session(session_report: SessionReport):
    vector_writer.upload_session_vector(session_report.patient_id,
                                        session_report.text,
                                        session_report.date)
    
    # Write full text to supabase
    # supabase = supabase_admin_instance()
    # supabase.table('session_reports').insert({
    #     "session_text": session_report.text,
    #     "session_date": session_report.date,
    #     "patient_id": session_report.patient_id,
    #     "therapist_id": session_report.therapist_id}).execute()

    return {"success": True}

@app.get("/v1/assistant-queries")
def execute_assistant_query(query: AssistantQuery):
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
def upload_session_notes_image(therapist_id: str = "",
                               patient_id: str = "",
                               image: UploadFile = File(...)):
    if therapist_id == "" or patient_id == "":
        return {"success": False, "error": "Need both a therapist id as well as a patient id"}

    url = os.getenv("DOCUPANDA_URL")
    api_key = os.getenv("DOCUPANDA_API_KEY")
    file_name, file_extension = os.path.splitext(image.filename)

    # Format name to be used for image copy with template 'therapist_id-patient_id-timestamp'
    image_data_dir = 'image-data'
    pdf_extension = '.pdf'
    image_copy_bare_name = therapist_id + '-' + patient_id + '-' + datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    image_copy_path = image_data_dir + '/' + image_copy_bare_name + file_extension
    image_copy_pdf_path = image_data_dir + '/' + image_copy_bare_name + pdf_extension
    files_to_clean = [image_copy_path]

    # Write incoming image to our DB for further processing
    with open(image_copy_path, 'wb+') as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Convert to PDF if necessary
    if file_extension.lower() != pdf_extension:
        Image.open(image_copy_path).convert('RGB').save(image_copy_pdf_path)
        files_to_clean.append(image_copy_pdf_path)

    if not os.path.exists(image_copy_pdf_path):
        os.remove(image_copy_path)
        return {"success": False,
            "message": f"Converting the image format to PDF caused issues"}
    
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

# Private funtions 

async def clean_up_images(images):
    for image in images:
        os.remove(image)

def supabase_admin_instance() -> Client:
    key: str = os.environ.get("SUPABASE_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    
    supabase: Client = create_client(url, key)
    supabase.auth.sign_in_with_password({"email": os.environ.get("SUPABASE_ADMIN_USERNAME"),
                                                    "password": os.environ.get("SUPABASE_ADMIN_PASSWORD")})

    return supabase
