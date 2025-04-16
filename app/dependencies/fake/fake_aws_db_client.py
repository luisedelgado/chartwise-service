from fastapi import Request
from typing import Any, List, Optional

from ..api.aws_db_base_class import AwsDbBaseClass
from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass
from ...internal.schemas import (ENCRYPTED_PATIENTS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
                                 ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
                                 ENCRYPTED_SESSION_REPORTS_TABLE_NAME,)

FAKE_USER_ID_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"

class FakeAwsDbClient(AwsDbBaseClass):

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

    async def insert(self,
                     user_id: str,
                     request: Request,
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        pass

    async def update(self,
                     user_id: str,
                     request: Request,
                     payload: dict[str, Any],
                     filters: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        pass

    async def upsert(self,
                     user_id: str,
                     request: Request,
                     conflict_columns: List[str],
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        pass

    async def select(self,
                     user_id: str,
                     request: Request,
                     fields: list[str],
                     filters: dict[str, Any],
                     table_name: str,
                     limit: Optional[int] = None,
                     order_by: Optional[tuple[str, str]] = None) -> list[dict]:
        pass

    async def select_with_stripe_connection(self,
                                            fields: list[str],
                                            filters: dict[str, Any],
                                            table_name: str,
                                            secret_manager: AwsSecretManagerBaseClass,
                                            limit: Optional[int] = None,
                                            order_by: Optional[tuple[str, str]] = None) -> list[dict]:
        pass

    async def delete(self,
                     user_id: str,
                     request: Request,
                     table_name: str,
                     filters: dict[str, Any]) -> list[dict]:
        pass

    async def get_user(self):
        pass

    async def get_current_user_id(self) -> str:
        pass

    async def sign_out(self):
        pass

    async def delete_user(self, user_id: str):
        pass

    async def set_session_user_id(self, request: Request, user_id: str):
        pass
