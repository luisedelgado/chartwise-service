from enum import Enum
from pydantic import BaseModel

from ..dependencies.api.docupanda_base_class import DocuPandaBaseClass
from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.pinecone_base_class import PineconeBaseClass
from ..dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass

class RouterDependencies:
    def __init__(self,
                 openai_client: OpenAIBaseClass = None,
                 pinecone_client: PineconeBaseClass = None,
                 docupanda_client: DocuPandaBaseClass = None,
                 supabase_client_factory: SupabaseFactoryBaseClass = None):
        self.openai_client = openai_client
        self.pinecone_client = pinecone_client
        self.docupanda_client = docupanda_client
        self.supabase_client_factory = supabase_client_factory

class SessionNotesSource(Enum):
    UNDEFINED = "undefined"
    FULL_SESSION_RECORDING = "full_session_recording"
    NOTES_RECORDING = "notes_recording"
    NOTES_IMAGE = "notes_image"
    MANUAL_INPUT = "manual_input"

class SessionNotesTemplate(Enum):
    FREE_FORM = "free_form"
    SOAP = "soap"

class SessionNotesInsert(BaseModel):
    therapist_id: str
    patient_id: str
    text: str
    date: str
    client_timezone_identifier: str
    source: SessionNotesSource

class SessionNotesUpdate(BaseModel):
    therapist_id: str
    date: str
    session_notes_id: str
    client_timezone_identifier: str
    source: SessionNotesSource
    diarization: str = None
    text: str

class TemplatePayload(BaseModel):
    session_notes_text: str
    template: SessionNotesTemplate = SessionNotesTemplate.SOAP
    therapist_id: str

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

class PatientConsentmentChannel(Enum):
    UNDEFINED = "undefined"
    VERBAL = "verbal"
    WRITTEN = "written"

class PatientInsertPayload(BaseModel):
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    pre_existing_history: str = None
    gender: Gender
    email: str
    phone_number: str
    consentment_channel: PatientConsentmentChannel
    therapist_id: str

class PatientUpdatePayload(BaseModel):
    patient_id: str
    first_name: str
    middle_name: str = None
    last_name: str
    birth_date: str
    pre_existing_history: str = None
    gender: Gender
    email: str
    phone_number: str
    consentment_channel: PatientConsentmentChannel
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
