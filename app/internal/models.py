from pydantic import BaseModel

class SessionReport(BaseModel):
    patient_id: str
    text: str
    date: str
    supabase_access_token: str
    supabase_refresh_token: str
    source: str

class AssistantQuery(BaseModel):
    patient_id: str
    text: str
    response_language_code: str
    supabase_access_token: str
    supabase_refresh_token: str

class AssistantGreeting(BaseModel):
    addressing_name: str
    response_language_code: str
    client_tz_identifier: str

class SignupData(BaseModel):
    user_email: str
    user_password: str
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    signup_mechanism: str
    language_preference: str
