from pydantic import BaseModel

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
    response_language_code: str
    supabase_access_token: str
    supabase_refresh_token: str

class AssistantGreeting(BaseModel):
    addressing_name: str
    response_language_code: str
