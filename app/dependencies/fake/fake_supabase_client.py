from pydantic import BaseModel

from .fake_supabase_session import FakeSession
from ..api.supabase_base_class import SupabaseBaseClass

FAKE_USER_ID_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"

class FakeSupabaseResult(BaseModel):
    data: list

class FakeSupabaseUser(BaseModel):
    user: dict

class FakeSupabaseClient(SupabaseBaseClass):

    FAKE_SESSION_NOTES_ID = "c8d981a1-b751-4d2e-8dd7-c6c873f41f40"
    FAKE_PATIENT_ID = "548a9c31-f5aa-4e42-b247-f43f24e53ef5"
    FAKE_THERAPIST_ID = "97fb3e40-df5b-4ca5-88d4-26d37d49fc8c"

    return_authenticated_session: bool = False
    fake_access_token: str = None
    fake_refresh_token: str = None
    fake_text: str = None
    select_returns_data: bool = False
    session_notes_return_empty_notes_text = False
    session_notes_return_soap_notes = False
    patient_query_returns_preexisting_history = False
    user_authentication_id = None
    invoked_refresh_session: bool = False
    select_default_briefing_has_different_pronouns: bool = False
    session_upload_processing_status: str = None

    def delete_file(self,
                    source_bucket: str,
                    storage_filepath: str):
        pass

    def download_file(self,
                      source_bucket: str,
                      storage_filepath: str):
        pass

    def upload_file(self,
                    destination_bucket: str,
                    storage_filepath: str,
                    content: str | bytes):
        pass

    def move_file_between_buckets(source_bucket: str,
                                  destination_bucket: str,
                                  file_path: str):
        pass

    def insert(self,
               payload: dict,
               table_name: str):
        if table_name == "session_reports":
            self.fake_text = self.fake_text if "notes_text" not in payload else payload["notes_text"]
            self.session_upload_processing_status = self.session_upload_processing_status if "processing_status" not in payload else payload["processing_status"]
            return FakeSupabaseResult(data=[{
                    "id": self.FAKE_SESSION_NOTES_ID
                }])
        if table_name == "patients":
            return FakeSupabaseResult(data=[{
                "id": self.FAKE_PATIENT_ID,
            }])
        else:
            pass

    def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        if table_name == "session_reports":
            self.fake_text = self.fake_text if "notes_text" not in payload else payload["notes_text"]
            self.session_upload_processing_status = self.session_upload_processing_status if "processing_status" not in payload else payload["processing_status"]
            return FakeSupabaseResult(data=[{
                    "id": self.FAKE_SESSION_NOTES_ID
                }])
        if table_name == "patients":
            return FakeSupabaseResult(data=[{
                "first_name": "Fake first name",
                "gender": "female",
            }])
        if table_name == "therapists":
            return FakeSupabaseResult(data=[{
                "first_name": "Fake first name",
                "gender": "female",
            }])
        else:
            pass

    def upsert(self,
               payload: dict,
               on_conflict: str,
               table_name: str):
        pass

    def select(self,
               fields: str,
               filters: dict,
               table_name: str,
               limit: int = None,
               order_desc_column: str = None):
        if not self.select_returns_data:
            return FakeSupabaseResult(data=[])

        if table_name == "therapists":
            return FakeSupabaseResult(data=[{
                "language_preference": "en-US",
                "first_name": "Fake first name",
                "gender": "female",
            }])
        if table_name == "subscription_status":
            return FakeSupabaseResult(data=[{
                "customer_id": FAKE_USER_ID_TOKEN,
                "subscription_id": self.FAKE_SESSION_NOTES_ID,
                "free_trial_end_date": "2025-01-12",
                "current_tier": "basic",
                "is_active": True,
                "data": [{
                    "suscription_id": self.FAKE_SESSION_NOTES_ID
                }]
            }])
        if table_name == "patients":
            return FakeSupabaseResult(data=[{
                "last_session_date":"2000-01-01",
                "total_sessions": 2,
                "first_name": "Fake first name",
                "last_name": "myLastName",
                "therapist_id": self.FAKE_THERAPIST_ID,
                "gender": "female",
                "pre_existing_history": "preExistingHistory" if self.patient_query_returns_preexisting_history else None
            }])
        if table_name == "session_reports":
            return FakeSupabaseResult(data=[{
                "id": self.FAKE_SESSION_NOTES_ID,
                "notes_mini_summary":"My fake mini summary",
                "notes_text": "My fake notes text" if not self.session_notes_return_empty_notes_text else "",
                "session_date": "2023-01-01",
                "patient_id": self.FAKE_PATIENT_ID,
                "therapist_id": self.FAKE_THERAPIST_ID,
                "template": "free_form" if not self.session_notes_return_soap_notes else "soap",
            }])
        if table_name == "textraction_logs":
            return FakeSupabaseResult(data=[{
            "session_id": "123",
            "therapist_id": self.FAKE_THERAPIST_ID,
        }])
        if table_name == "user_interface_strings":
            return FakeSupabaseResult(data=[{
                "value": "fake_string"
            }])
        if table_name == "patient_topics":
            return FakeSupabaseResult(data=[{
                "value": "fake_string"
            }])
        if table_name == "patient_question_suggestions":
            return FakeSupabaseResult(data=[{
                "value": "fake_string"
            }])
        if table_name == "patient_briefings":
            return FakeSupabaseResult(data=[{
                "value": "fake_string"
            }])
        if table_name == "patient_attendance":
            return FakeSupabaseResult(data=[{
                "value": "fake_string"
            }])
        if table_name == "static_default_briefings":
            if self.select_default_briefing_has_different_pronouns:
                return FakeSupabaseResult(data=[{
                    "value": {
                        "briefings": {
                            "has_different_pronouns": "true",
                            "new_patient": {
                                "male_pronouns": {
                                    "value": r"Hi {user_first_name}, this is the fake briefing for {patient_first_name}"
                                },
                                "female_pronouns": {
                                    "value": r"Hi {user_first_name}, this is the fake briefing for {patient_first_name}"
                                }
                            },
                            "existing_patient": {
                                "male_pronouns": {
                                    "value": r"Hi {user_first_name}, this is the fake briefing for {patient_first_name}"
                                },
                                "female_pronouns": {
                                    "value": r"Hi {user_first_name}, this is the fake briefing for {patient_first_name}"
                                }
                            }
                        }
                    }
                }])
            else:
                return FakeSupabaseResult(data=[{
                    "value": {
                        "briefings": {
                            "new_patient": {
                                "value": r"Hi {user_first_name}, this is the fake briefing for {patient_first_name}"
                            },
                            "existing_patient": {
                                "value": r"Hi {user_first_name}, this is the fake briefing for {patient_first_name}"
                            }
                        }
                    }
                }])

        raise Exception("Untracked table name")

    def select_within_range(self,
                            fields: str,
                            filters: dict,
                            table_name: str,
                            range_start: str,
                            range_end: str,
                            column_marker: str,
                            limit: int = None):
        if not self.select_returns_data:
            return FakeSupabaseResult(data=[])

        if table_name == "session_reports":
            return FakeSupabaseResult(data=[{
                "id": self.FAKE_SESSION_NOTES_ID,
                "notes_mini_summary":"My fake mini summary",
                "notes_text": "My fake notes text" if not self.session_notes_return_empty_notes_text else "",
                "session_date": "2023-01-01",
                "patient_id": self.FAKE_PATIENT_ID,
                "therapist_id": self.FAKE_THERAPIST_ID,
                "template": "free_form" if not self.session_notes_return_soap_notes else "soap",
            }])
        raise Exception("Untracked table name")

    def select_batch_where_is_not_null(self,
                                       table_name: str,
                                       fields: str,
                                       batch_start: int,
                                       batch_end: int,
                                       non_null_column: str = None,
                                       order_ascending_column: str = None):
        pass

    def select_either_or_from_column(self,
                                     fields: str,
                                     possible_values: list,
                                     table_name: str,
                                     order_desc_column: str = None):
        if table_name == "user_interface_strings":
            return FakeSupabaseResult(data=[{
                "value": "fake_string"
            }])

    def delete(self,
               filters: dict,
               table_name: str):
        return FakeSupabaseResult(data=[{
            "therapist_id": self.FAKE_THERAPIST_ID,
            "patient_id": self.FAKE_PATIENT_ID,
            "session_date": "2023-01-01",
        }])

    def delete_where_is_not(self,
                            is_not_filters: dict,
                            table_name: str):
        return FakeSupabaseResult(data=[{
            "therapist_id": self.FAKE_THERAPIST_ID,
            "patient_id": self.FAKE_PATIENT_ID,
            "session_date": "2023-01-01",
        }])

    def get_user(self):
        return FakeSupabaseUser(user={
            'id': self.user_authentication_id
        })

    def get_current_user_id(self) -> str:
        return self.FAKE_THERAPIST_ID

    def refresh_session(self):
        self.invoked_refresh_session = True
        return FakeSession(return_authenticated_session=self.return_authenticated_session,
                           fake_access_token=self.fake_access_token,
                           fake_refresh_token=self.fake_refresh_token)

    def sign_out(self):
        pass

    def sign_in(self, email: str, password: str) -> dict:
        if not self.return_authenticated_session:
            return {}
        return {
            "user": {
                "id": FAKE_USER_ID_TOKEN
            }
        }
