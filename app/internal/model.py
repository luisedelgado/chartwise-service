from enum import Enum
from pydantic import BaseModel

class SessionNotesSource(Enum):
    UNDEFINED = "undefined"
    FULL_SESSION_RECORDING = "full_session_recording"
    NOTES_RECORDING = "notes_recording"
    NOTES_IMAGE = "notes_image"
    MANUAL_INPUT = "manual_input"

class SessionNotesInsert(BaseModel):
    therapist_id: str
    patient_id: str
    text: str
    date: str
    source: SessionNotesSource

class SessionNotesUpdate(BaseModel):
    therapist_id: str
    patient_id: str
    date: str
    session_notes_id: str
    source: SessionNotesSource
    diarization: str = None
    text: str

class AssistantQuery(BaseModel):
    patient_id: str
    therapist_id: str
    text: str

class Gender(Enum):
    UNDEFINED = "undefined"
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    RATHER_NOT_SAY = "rather_not_say"

class LoginData(BaseModel):
    datastore_access_token: str = None
    datastore_refresh_token: str = None
    user_id: str

class LogoutData(BaseModel):
    therapist_id: str

class TextractionData(BaseModel):
    therapist_id: str
    patient_id: str
    document_id: str

class Greeting(BaseModel):
    addressing_name: str
    client_tz_identifier: str
    therapist_id: str

class SummaryConfiguration(Enum):
    UNDEFINED = "undefined"
    PRIMARY_TOPICS = "primary_topics"
    EMOTIONAL_STATE = "emotional_state"
    SYMPTOMS = "symptoms"
    FULL_SUMMARY = "full_summary"

class SessionHistorySummary(BaseModel):
    therapist_id: str
    patient_id: str
    summary_configuration: SummaryConfiguration

class QuestionSuggestionsParams(BaseModel):
    therapist_id: str
    patient_id: str

class PatientConsentmentChannel(Enum):
    UNDEFINED = "undefined"
    VERBAL = "verbal"
    WRITTEN = "written"

class PatientInsertPayload(BaseModel):
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    gender: Gender
    email: str
    phone_number: str
    consentment_channel: PatientConsentmentChannel
    therapist_id: str

class PatientUpdatePayload(BaseModel):
    id: str
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    gender: Gender
    email: str
    phone_number: str
    consentment_channel: PatientConsentmentChannel
    therapist_id: str

class PatientDeletePayload(BaseModel):
    patient_id: str
    therapist_id: str

class SignupMechanism(Enum):
    UNDEFINED = "undefined"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    INTERNAL = "internal"

class TherapistInsertPayload(BaseModel):
    id: str
    email: str
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    signup_mechanism: SignupMechanism
    language_code_preference: str
    gender: Gender

class TherapistUpdatePayload(BaseModel):
    id: str
    email: str
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    language_code_preference: str
    gender: Gender

class SessionRefreshData():
    def __init__(self, session_id, auth_token, datastore_access_token = None, datastore_refresh_token = None):
        self._session_id = session_id
        self._auth_token = auth_token
        self._datastore_access_token = datastore_access_token
        self._datastore_refresh_token = datastore_refresh_token
