from pydantic import BaseModel

from ..api.aws_db_base_class import AwsDbBaseClass
from ...internal.schemas import (ENCRYPTED_PATIENTS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
                                 ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
                                 ENCRYPTED_SESSION_REPORTS_TABLE_NAME,)

FAKE_USER_ID_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"

class FakeSupabaseClient(AwsDbBaseClass):

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
    user_authentication_email = None
    invoked_refresh_session: bool = False
    select_default_briefing_has_different_pronouns: bool = False
    session_upload_processing_status: str = None

    async def delete_user(self, user_id: str):
        pass

    async def insert(self,
               payload: dict,
               table_name: str):
        pass

    async def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        pass

    async def upsert(self,
               payload: dict,
               on_conflict: str,
               table_name: str):
        pass

    async def select(self,
               fields: str,
               filters: dict,
               table_name: str,
               limit: int = None,
               order_desc_column: str = None):
        pass

    async def delete(self,
               filters: dict,
               table_name: str):
        pass

    async def delete_where_is_not(self,
                            is_not_filters: dict,
                            table_name: str):
        pass

    async def get_user(self):
        pass

    async def get_current_user_id(self) -> str:
        pass

    async def sign_out(self):
        pass
