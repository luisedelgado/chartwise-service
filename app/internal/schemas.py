from enum import Enum

# Encrypted tables names
ENCRYPTED_PATIENTS_TABLE_NAME = "encrypted_patients"
ENCRYPTED_SESSION_REPORTS_TABLE_NAME = "encrypted_session_reports"
ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME = "encrypted_patient_attendance"
ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME = "encrypted_patient_briefings"
ENCRYPTED_PATIENT_TOPICS_TABLE_NAME = "encrypted_patient_topics"
ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME = "encrypted_patient_question_suggestions"
ENCRYPTED_TABLES = [ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
                    ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
                    ENCRYPTED_PATIENTS_TABLE_NAME,
                    ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
                    ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
                    ENCRYPTED_SESSION_REPORTS_TABLE_NAME]

# Encryped columns per table
IS_JSON_KEY = "is_json"
PATIENT_ATTENDANCE_ENCRYPTED_COLUMNS = {"insights": {IS_JSON_KEY: False},}
PATIENT_BRIEFINGS_ENCRYPTED_COLUMNS = {"briefing": {IS_JSON_KEY: False},}
PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS = {"questions": {IS_JSON_KEY: True},}
PATIENT_TOPICS_ENCRYPTED_COLUMNS = { "topics": {
                                        IS_JSON_KEY: True
                                    },"insights": {
                                        IS_JSON_KEY: False
                                    },}
PATIENTS_ENCRYPTED_COLUMNS = { "first_name": {
                                IS_JSON_KEY: False
                             },"last_name": {
                                IS_JSON_KEY: False
                             },"birth_date": {
                                IS_JSON_KEY: False
                             },"gender": {
                                IS_JSON_KEY: False
                             },"email": {
                                IS_JSON_KEY: False
                             },"phone_number": {
                                IS_JSON_KEY: False
                             },"pre_existing_history": {
                                IS_JSON_KEY: False
                             },}
SESSION_REPORTS_ENCRYPTED_COLUMNS = { "notes_text": {
                                        IS_JSON_KEY: False
                                    },"diarization": {
                                        IS_JSON_KEY: True
                                    },"notes_mini_summary": {
                                        IS_JSON_KEY: False
                                    }}

TESTING_ENVIRONMENT = "testing"
DEV_ENVIRONMENT = "dev"
STAGING_ENVIRONMENT = "staging"
PROD_ENVIRONMENT = "prod"

class Gender(Enum):
    UNDEFINED = "undefined"
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    RATHER_NOT_SAY = "rather_not_say"

class SessionProcessingStatus(Enum):
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class MediaType(Enum):
    IMAGE = "image"
    AUDIO = "audio"

class TimeRange(Enum):
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
