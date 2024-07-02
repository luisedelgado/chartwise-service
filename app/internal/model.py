from pydantic import BaseModel

class SessionNotesInsert(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    date: str
    datastore_access_token: str
    datastore_refresh_token: str
    source: str

class SessionNotesUpdate(BaseModel):
    patient_id: str
    therapist_id: str
    session_notes_id: str
    diarization: str = None
    text: str
    datastore_access_token: str
    datastore_refresh_token: str

class SessionNotesDelete(BaseModel):
    patient_id: str
    therapist_id: str
    session_notes_id: str
    datastore_access_token: str
    datastore_refresh_token: str

class AssistantQuery(BaseModel):
    patient_id: str
    therapist_id: str
    text: str
    response_language_code: str
    datastore_access_token: str
    datastore_refresh_token: str

class SignupData(BaseModel):
    user_email: str
    user_password: str
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    signup_mechanism: str
    language_preference: str

class LogoutData(BaseModel):
    therapist_id: str

class TextractionData(BaseModel):
    therapist_id: str
    patient_id: str
    document_id: str

class Greeting(BaseModel):
    addressing_name: str
    response_language_code: str
    client_tz_identifier: str
    therapist_id: str

class SessionHistorySummary(BaseModel):
    therapist_id: str
    patient_id: str
    response_language_code: str
    datastore_access_token: str
    datastore_refresh_token: str

class SessionRefreshData():
    def __init__(self, session_id, auth_token):
        self._session_id = session_id
        self._auth_token = auth_token
