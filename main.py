import query as query_handler
import vector_writer as vector_writer
from fastapi import FastAPI
from pydantic import BaseModel

class SessionReport(BaseModel):
    index_name: str
    text: str
    date: str
    
class AssistantQuery(BaseModel):
    index_name: str
    text: str
    
class Patient(BaseModel):
    id: str

app = FastAPI()

@app.post("/v1/sessions")
def upload_new_session(session_report: SessionReport):
    vector_writer.upload_session_vector(session_report.index_name,
                                        session_report.text,
                                        session_report.date)
    return {"success": True}

@app.get("/v1/assistant-queries")
def execute_assistant_query(query: AssistantQuery):
    response = query_handler.query_model(query.index_name, query.text)
    return {"success": True,
            "response": response}
    
@app.post("/v1/patients")
def create_patient(patient: Patient):
    response = vector_writer.create_index(patient.id)
    return {"success": True}