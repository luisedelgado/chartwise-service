import json

from datetime import date
from fastapi import Request
from typing import Any, List, Optional

from ..api.aws_db_base_class import AwsDbBaseClass
from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass
from ..api.resend_base_class import ResendBaseClass
from ...internal.schemas import (
    ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
    ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
    ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
    ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
    ENCRYPTED_PATIENTS_TABLE_NAME,
    ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
    SUBSCRIPTION_STATUS_TABLE_NAME,
    THERAPISTS_TABLE_NAME,
)

class FakeAwsDbClient(AwsDbBaseClass):

    FAKE_SESSION_NOTES_ID = "c8d981a1-b751-4d2e-8dd7-c6c873f41f40"
    FAKE_PATIENT_ID = "548a9c31-f5aa-4e42-b247-f43f24e53ef5"
    FAKE_THERAPIST_ID = "97fb3e40-df5b-4ca5-88d4-26d37d49fc8c"
    select_returns_data: bool = True
    patient_unique_active_years_nonzero: bool = True
    invoked_delete_patients = False

    async def insert(
        self,
        user_id: str,
        request: Request,
        payload: dict[str, Any],
        table_name: str
    ) -> Optional[dict]:
        if not self.select_returns_data:
            return {}

        if table_name == ENCRYPTED_PATIENTS_TABLE_NAME:
            return {
                "id": self.FAKE_PATIENT_ID,
                "first_name": "foo",
                "last_name": "bar",
            }
        if table_name == ENCRYPTED_SESSION_REPORTS_TABLE_NAME:
            return {
                "id": self.FAKE_SESSION_NOTES_ID,
                "patient_id": self.FAKE_PATIENT_ID,
                "therapist_id": self.FAKE_THERAPIST_ID,
            }

    async def update(
        self,
        user_id: str,
        request: Request,
        payload: dict[str, Any],
        filters: dict[str, Any],
        table_name: str
    ) -> Optional[dict]:
        if table_name == THERAPISTS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_THERAPIST_ID,
                    "email": "myFakeEmail",
                    "first_name": "foo",
                    "last_name": "bar",
                    "language_preference": "en-US",
                    "gender": "male",
                },
            ]
        if table_name == ENCRYPTED_SESSION_REPORTS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                    "patient_id": self.FAKE_PATIENT_ID,
                    "therapist_id": self.FAKE_THERAPIST_ID,
                    "session_date": date(2024, 10, 10),
                    "notes_text": "These are my notes",
                    "template": "soap"
                }
            ]
        if table_name == ENCRYPTED_PATIENTS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_PATIENT_ID,
                    "first_name": "foo",
                    "last_name": "bar",
                    "therapist_id": self.FAKE_THERAPIST_ID,
                }
            ]
        return []

    async def upsert(
        self,
        user_id: str,
        request: Request,
        conflict_columns: List[str],
        payload: dict[str, Any],
        table_name: str
    ) -> Optional[dict]:
        pass

    async def select(
        self,
        user_id: str,
        request: Request,
        fields: list[str],
        filters: dict[str, Any],
        table_name: str,
        limit: Optional[int] = None,
        order_by: Optional[tuple[str, str]] = None
    ) -> list[dict]:
        if not self.select_returns_data:
            return {}

        if table_name == "user_interface_strings":
            return [
                {
                    "value": "myFakeValue",
                },
            ]
        if table_name == "static_default_briefings":
            inner_value = {
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

            return [{
                "value": json.dumps(inner_value)
            }]
        if table_name == ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                },
            ]
        if table_name == ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                },
            ]
        if table_name == ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                }
            ]
        if table_name == ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                }
            ]
        if table_name == ENCRYPTED_PATIENT_TOPICS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                }
            ]
        if table_name == ENCRYPTED_PATIENTS_TABLE_NAME:
            unique_active_years = ["2023", "2024"] if self.patient_unique_active_years_nonzero else []
            return [
                {
                    "id": self.FAKE_PATIENT_ID,
                    "first_name": "foo",
                    "last_name": "bar",
                    "gender": "female",
                    "total_sessions": 12,
                    "last_session_date": date(2024, 10, 10),
                    "onboarding_first_time_patient": True,
                    "unique_active_years": unique_active_years,
                    "pre_existing_history": "My fake history",
                },
            ]
        if table_name == ENCRYPTED_SESSION_REPORTS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                    "patient_id": self.FAKE_PATIENT_ID,
                    "therapist_id": self.FAKE_THERAPIST_ID,
                    "session_date": date(2024, 10, 10),
                    "notes_text": "",
                    "template": "soap"
                }
            ]
        if table_name == THERAPISTS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_THERAPIST_ID,
                    "email": "myFakeEmail",
                    "first_name": "foo",
                    "last_name": "bar",
                    "language_preference": "en-US",
                    "gender": "male",
                },
            ]
        if table_name == SUBSCRIPTION_STATUS_TABLE_NAME:
            return [
                {
                    "subscription_id": self.FAKE_SESSION_NOTES_ID,
                    "is_active": True,
                    "customer_id": "myFakeCustomerId",
                    "subscription_status": "active",
                    "current_tier": "premium",
                    "free_trial_end_date": date(2024, 10, 10),
                    "reached_tier_usage_limit": False,
                },
            ]

    async def select_with_stripe_connection(
        self,
        resend_client: ResendBaseClass,
        fields: list[str],
        filters: dict[str, Any],
        table_name: str,
        secret_manager: AwsSecretManagerBaseClass,
        limit: Optional[int] = None,
        order_by: Optional[tuple[str, str]] = None
    ) -> list[dict]:
        if not self.select_returns_data:
            return {}

        return {}

    async def delete(
        self,
        user_id: str,
        request: Request,
        table_name: str,
        filters: dict[str, Any]
    ) -> list[dict]:
        if not self.select_returns_data:
            return {}

        if table_name == ENCRYPTED_SESSION_REPORTS_TABLE_NAME:
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                    "patient_id": self.FAKE_PATIENT_ID,
                    "therapist_id": self.FAKE_THERAPIST_ID,
                    "session_date": date(2024, 10, 10),
                },
            ]
        if table_name == ENCRYPTED_PATIENTS_TABLE_NAME:
            self.invoked_delete_patients = True
            return [
                {
                    "id": self.FAKE_SESSION_NOTES_ID,
                },
            ]

    async def set_session_user_id(
        self,
        request: Request,
        user_id: str
    ):
        pass
