from pydantic import BaseModel

from .fake_supabase_session import FakeSession
from ..api.supabase_base_class import SupabaseBaseClass

FAKE_SESSION_NOTES_ID = "c8d981a1-b751-4d2e-8dd7-c6c873f41f40"
FAKE_PATIENT_ID = "548a9c31-f5aa-4e42-b247-f43f24e53ef5"
FAKE_THERAPIST_ID = "97fb3e40-df5b-4ca5-88d4-26d37d49fc8c"

class FakeSupabaseResult(BaseModel):
    data: list

class FakeSupabaseUser(BaseModel):
    user: dict

class FakeSupabaseClient(SupabaseBaseClass):

    return_authenticated_session: bool = False
    fake_access_token: str = None
    fake_refresh_token: str = None
    fake_text: str = None
    select_returns_data: bool = False
    patient_query_returns_preexisting_history = False
    user_authentication_id = None

    def insert(self,
               payload: dict,
               table_name: str):
        if table_name == "session_reports":
            self.fake_text = None if "notes_text" not in payload else payload["notes_text"]
            return FakeSupabaseResult(data=[{
                    "id": FAKE_SESSION_NOTES_ID
                }])
        if table_name == "patients":
            return FakeSupabaseResult(data=[{
                "id": FAKE_PATIENT_ID,
            }])
        else:
            ...

    def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        if table_name == "session_reports":
            self.fake_text = None if "notes_text" not in payload else payload["notes_text"]
            return FakeSupabaseResult(data=[{
                    "id": FAKE_SESSION_NOTES_ID
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
            ...

    def select(self,
               fields: str,
               filters: dict,
               table_name: str,
               order_desc_column: str = None):
        if not self.select_returns_data:
            return FakeSupabaseResult(data=[])

        if table_name == "therapists":
            return FakeSupabaseResult(data=[{
                "language_preference": "en-US",
                "first_name": "Fake first name",
                "gender": "female",
            }])
        if table_name == "patients":
            return FakeSupabaseResult(data=[{
                "last_session_date":"2000-01-01",
                "total_sessions": 2,
                "first_name": "Fake first name",
                "last_name": "myLastName",
                "therapist_id": FAKE_THERAPIST_ID,
                "gender": "female",
                "pre_existing_history": "preExistingHistory" if self.patient_query_returns_preexisting_history else None
            }])
        if table_name == "session_reports":
            return FakeSupabaseResult(data=[{
                "notes_mini_summary":"My fake mini summary",
                "notes_text": "My fake notes text",
                "session_date": "2023-01-01",
                "patient_id": FAKE_PATIENT_ID,
                "therapist_id": FAKE_THERAPIST_ID,
                "diarization_template": "free_form",
            }])
        if table_name == "diarization_logs":
            return FakeSupabaseResult(data=[{
            "session_id": "123",
            "therapist_id": FAKE_THERAPIST_ID,
        }])
        if table_name == "user_interface_strings":
            return FakeSupabaseResult(data=[{
                "value": "fake_string"
            }])

        raise Exception("Untracked table name")

    def select_either_or_from_column(self,
                                     fields: str,
                                     column_name: str,
                                     possible_values: list,
                                     table_name: str,
                                     order_desc_column: str = None):
        pass

    def delete(self,
               filters: dict,
               table_name: str):
        return FakeSupabaseResult(data=[{
            "therapist_id": FAKE_THERAPIST_ID,
            "patient_id": FAKE_PATIENT_ID,
            "session_date": "2023-01-01",
        }])

    def get_user(self):
        return FakeSupabaseUser(user={
            'id': self.user_authentication_id
        })

    def get_current_user_id(self) -> str:
        return FAKE_THERAPIST_ID

    def refresh_session(self):
        return FakeSession(return_authenticated_session=self.return_authenticated_session,
                           fake_access_token=self.fake_access_token,
                           fake_refresh_token=self.fake_refresh_token)

    def sign_out(self):
        pass
