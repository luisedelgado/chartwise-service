from pydantic import BaseModel

class SessionNotesInsert(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    date: str
    supabase_access_token: str
    supabase_refresh_token: str
    source: str

class SessionNotesUpdate(BaseModel):
    patient_id: str
    therapist_id: str
    session_notes_id: str
    diarization: str = None
    text: str
    supabase_access_token: str
    supabase_refresh_token: str

class AssistantQuery(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    response_language_code: str
    supabase_access_token: str
    supabase_refresh_token: str

class SignupData(BaseModel):
    user_email: str
    user_password: str
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    signup_mechanism: str
    language_preference: str
