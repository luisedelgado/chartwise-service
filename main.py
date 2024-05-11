import base64, os, pathlib, requests
import query as query_handler
import vector_writer as vector_writer
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from PIL import Image

class SessionReport(BaseModel):
    index_name: str
    text: str
    date: str
    
class AssistantQuery(BaseModel):
    index_id: str
    text: str
    
class Patient(BaseModel):
    id: str

class ImageItem(BaseModel):
    document_id: str

app = FastAPI()

@app.post("/v1/sessions")
def upload_new_session(session_report: SessionReport):
    vector_writer.upload_session_vector(session_report.index_name,
                                        session_report.text,
                                        session_report.date)
    return {"success": True}

@app.get("/v1/assistant-queries")
def execute_assistant_query(query: AssistantQuery):
    response = query_handler.query_store(query.index_id, query.text)
    return {"success": True,
            "response": response}
    
@app.post("/v1/patients")
def create_patient(patient: Patient):
    response = vector_writer.create_index(patient.id)
    return {"success": True}

@app.get("/v1/greetings")
def fetch_greeting():
    return {"success": True, "message": query_handler.create_greeting()}

@app.get("/v1/healthcheck")
def read_healthcheck():
     return {"status": "ok"}

@app.post("/v1/image-files")
def upload_session_notes_image(file: UploadFile = File(...)):
    url = os.getenv("DOCUPANDA_URL")
    api_key = os.getenv("DOCUPANDA_API_KEY")
    
    image_data_dir = 'image-data'
    data_dir_with_file = pathlib.Path(image_data_dir, file.filename)
    full_path = pathlib.Path(os.getcwd(), data_dir_with_file)

    # Write incoming image to our server for further processing
    try:
        contents = file.file.read()
        with open(full_path, 'wb') as f:
            f.write(contents)
    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        file.file.close()
        
    file_name, file_extension = os.path.splitext(full_path)

    # Convert to PDF if necessary
    if file_extension.lower() != ".pdf":
        pdf_file = file_name + ".pdf"
        data_dir_with_pdf = pathlib.Path(image_data_dir, pdf_file)
        pdf_save_path = pathlib.Path(os.getcwd(), data_dir_with_pdf)
        save_as_pdf(Image.open(full_path), pdf_save_path)
    
    if not os.path.exists(pdf_save_path):
        return {"success": False,
            "message": f"The image format caused issues"}
    
    # Send to DocuPanda
    payload = {"document": {"file": {
        "contents": base64.b64encode(open(pdf_save_path, 'rb').read()).decode(),
        "filename": file.filename
    }}}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-API-Key": api_key
    }

    response = requests.post(url, json=payload, headers=headers)
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

# Pragma mark - Private

def save_as_pdf(raw_image, pdf_save_location):
    rgb_image = raw_image.convert('RGB')
    rgb_image.save(pdf_save_location)
