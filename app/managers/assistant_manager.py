import asyncio, json, os

from collections import Counter
from datetime import date, datetime, timedelta
from enum import Enum
from fastapi import BackgroundTasks, Request
from pydantic import BaseModel
from typing import Any, AsyncIterable, Set

from ..dependencies.dependency_container import AwsDbBaseClass, dependency_container
from ..dependencies.api.pinecone_session_date_override import (
    PineconeQuerySessionDateOverride,
    PineconeQuerySessionDateOverrideType,
)
from ..managers.auth_manager import AuthManager
from ..internal.alerting.internal_alert import EngineeringAlert
from ..internal.schemas import (
    DATE_COLUMNS,
    ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
    ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
    ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
    ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
    ENCRYPTED_PATIENTS_TABLE_NAME,
    ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
    VECTORS_SESSION_MAPPINGS_TABLE_NAME,
    Gender,
    SessionProcessingStatus,
    TimeRange
)
from ..internal.utilities import datetime_handler, general_utilities
from ..vectors.chartwise_assistant import (
    ChartWiseAssistant,
    ListRecentTopicsSchema,
    ListQuestionSuggestionsSchema,
)

class AssistantQuery(BaseModel):
    patient_id: str
    text: str

class SessionCrudOperation(Enum):
    INSERT_COMPLETED = "insert_completed"
    UPDATE_COMPLETED = "update_completed"
    DELETE_COMPLETED = "delete_completed"

class PatientConsentmentChannel(Enum):
    UNDEFINED = "undefined"
    NO_CONSENT = "no_consent"
    VERBAL = "verbal"
    WRITTEN = "written"

class SessionNotesSource(Enum):
    UNDEFINED = "undefined"
    FULL_SESSION_RECORDING = "full_session_recording"
    NOTES_RECORDING = "notes_recording"
    NOTES_IMAGE = "notes_image"
    MANUAL_INPUT = "manual_input"

class PatientInsertPayload(BaseModel):
    first_name: str
    last_name: str
    birth_date: str | None = None
    pre_existing_history: str | None = None
    gender: Gender | None = None
    email: str | None = None
    phone_number: str | None = None
    consentment_channel: PatientConsentmentChannel | None = None
    onboarding_first_time_patient: bool

class PatientUpdatePayload(BaseModel):
    id: str
    first_name: str | None = None
    last_name: str | None = None
    birth_date: str | None = None
    pre_existing_history: str | None = None
    gender: Gender | None = None
    email: str | None = None
    phone_number: str | None = None
    consentment_channel: PatientConsentmentChannel | None = None

class SessionNotesInsert(BaseModel):
    patient_id: str
    notes_text: str
    session_date: str

class SessionNotesUpdate(BaseModel):
    id: str
    notes_text: str | None = None
    session_date: str | None = None
    diarization: str | None = None
    is_read: bool | None = None

class CachedPatientQueryData:
    def __init__(self,
                 patient_id: str,
                 patient_first_name: str,
                 patient_last_name: str,
                 response_language_code: str,
                 patient_gender: str | None = None,
                 last_session_date: date | None = None):
        self.patient_id = patient_id
        self.patient_first_name = patient_first_name
        self.patient_last_name = patient_last_name
        self.patient_gender = patient_gender
        self.last_session_date = last_session_date
        self.response_language_code = response_language_code

class AssistantManager:

    cached_patient_query_data: CachedPatientQueryData | None = None

    def __init__(self):
        self.chartwise_assistant = ChartWiseAssistant()

    async def retrieve_single_session_report(
        self,
        therapist_id: str,
        session_report_id: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                fields=["*"],
                filters={
                    "id": session_report_id,
                    "is_soft_deleted": False,
                }
            )
            return {} if len(response) == 0 else response[0]
        except Exception as e:
            raise RuntimeError(e) from e

    async def retrieve_session_reports(
        self,
        therapist_id: str,
        patient_id: str,
        year: str,
        time_range: TimeRange | None,
        most_recent: int,
        request: Request,
    ):
        try:
            if year:
                return await self._retrieve_sessions_for_year(
                    therapist_id=therapist_id,
                    request=request,
                    patient_id=patient_id,
                    year=year
                )
            if most_recent:
                return await self._retrieve_n_most_recent_sessions(
                    therapist_id=therapist_id,
                    request=request,
                    patient_id=patient_id,
                    most_recent_n=most_recent
                )
            if time_range:
                return await self._retrieve_sessions_in_range(
                    request=request,
                    patient_id=patient_id,
                    time_range=time_range,
                    therapist_id=therapist_id
                )

            raise ValueError("One of 'year', 'recent', or 'range' must be provided.")
        except Exception as e:
            raise RuntimeError(e) from e

    async def process_new_session_data(
        self,
        environment: str,
        language_code: str,
        background_tasks: BackgroundTasks,
        auth_manager: AuthManager,
        patient_id: str,
        notes_text: str,
        session_date: date,
        source: SessionNotesSource,
        session_id: str | None,
        therapist_id: str,
        request: Request,
        diarization: str | None = None
    ) -> str:
        try:
            assert source == SessionNotesSource.MANUAL_INPUT, f"Unexpected SessionNotesSource value \"{source.value}\""
            now_timestamp = datetime.now()
            insert_payload = {
                "notes_text": notes_text,
                "notes_mini_summary": "-",
                "session_date": session_date,
                "patient_id": patient_id,
                "source": source.value,
                "last_updated": now_timestamp,
                "therapist_id": therapist_id,
                "processing_status": SessionProcessingStatus.SUCCESS.value
            }

            if len(diarization or '') > 0:
                insert_payload['diarization'] = diarization

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            insert_result = await aws_db_client.insert(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                payload=insert_payload
            )
            assert type(insert_result) == dict, "Unexpected type after inserting"
            session_notes_id = insert_result['id']

            # Upload vector embeddings and generate insights
            background_tasks.add_task(
                self._insert_vectors_and_generate_insights,
                session_notes_id=session_notes_id,
                therapist_id=therapist_id,
                patient_id=patient_id,
                notes_text=notes_text,
                session_date=session_date,
                session_id=session_id,
                language_code=language_code,
                environment=environment,
                background_tasks=background_tasks,
                auth_manager=auth_manager,
                request=request,
            )
            return session_notes_id
        except Exception as e:
            raise RuntimeError(e) from e

    async def update_session(
        self,
        therapist_id: str,
        language_code: str,
        environment: str,
        background_tasks: BackgroundTasks,
        auth_manager: AuthManager,
        filtered_body: dict,
        session_id: str | None,
        request: Request,
    ):
        try:
            session_notes_id = filtered_body['id']
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            report_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                filters={
                    'id': session_notes_id
                }
            )
            assert (0 != len(report_query)), "There isn't a match with the incoming session data."

            # Start populating payload for updating session.
            session_update_payload: dict[str, Any] = {
                "last_updated": datetime.now()
            }

            for key, value in filtered_body.items():
                if key == 'id':
                    continue
                if isinstance(value, Enum):
                    value = value.value
                elif key in DATE_COLUMNS and type(value) == str:
                    value = datetime.strptime(
                        value,
                        datetime_handler.DATE_FORMAT
                    ).date()
                session_update_payload[key] = value

            session_update_response = await aws_db_client.update(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                payload=session_update_payload,
                filters={
                    'id': session_notes_id
                }
            )
            assert (0 != len(session_update_response or '')), "Update operation could not be completed"

            current_session_text = report_query[0]['notes_text']
            current_session_date: date = report_query[0]['session_date']
            session_text_changed = 'notes_text' in session_update_payload and session_update_payload['notes_text'] != current_session_text
            session_date_changed = (
                'session_date' in session_update_payload and session_update_payload['session_date'] != current_session_date
            )

            # Update the session vectors if needed
            patient_id = str(report_query[0]['patient_id'])
            if session_date_changed or session_text_changed:
                new_session_date = filtered_body.get('session_date', None)
                background_tasks.add_task(
                    self._update_vectors_and_generate_insights,
                    session_notes_id=session_notes_id,
                    therapist_id=therapist_id,
                    patient_id=patient_id,
                    notes_text=filtered_body.get('notes_text', current_session_text),
                    old_session_date=current_session_date,
                    new_session_date=(
                        datetime.strptime(
                            new_session_date,
                            datetime_handler.DATE_FORMAT
                        ).date() if new_session_date is not None
                        else current_session_date
                    ),
                    session_id=session_id,
                    language_code=language_code,
                    environment=environment,
                    background_tasks=background_tasks,
                    auth_manager=auth_manager,
                    request=request,
                )

            return {
                "patient_id": patient_id,
                "session_report_id": session_notes_id
            }
        except Exception as e:
            raise RuntimeError(e) from e

    async def delete_session(
        self,
        language_code: str,
        environment: str,
        session_id: str | None,
        background_tasks: BackgroundTasks,
        therapist_id: str,
        session_report_id: str,
        request: Request,
    ):
        try:
            # Soft-delete the session report given our 6-year HIPAA retention policy.
            soft_deletion_result_data = await dependency_container.inject_aws_db_client().update(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                payload={
                    "is_soft_deleted": True,
                    "soft_deleted_at": datetime.now()
                },
                filters={
                    'id': session_report_id
                },
            )
            assert type(soft_deletion_result_data) is list and len(soft_deletion_result_data) > 0, "No session found with the incoming session_report_id"

            therapist_id = str(soft_deletion_result_data[0]['therapist_id'])
            patient_id = str(soft_deletion_result_data[0]['patient_id'])
            session_date = soft_deletion_result_data[0]['session_date']

            # Delete all vector data for the patient, since it's not necessary to keep around
            # when we already have our soft-deleted records in Postgres.
            background_tasks.add_task(
                self._delete_vectors_and_generate_insights,
                therapist_id=therapist_id,
                patient_id=patient_id,
                session_date=session_date,
                session_id=session_id,
                language_code=language_code,
                environment=environment,
                background_tasks=background_tasks,
                request=request,
            )

            return {
                "patient_id": patient_id,
                "session_report_id": session_report_id,
            }
        except Exception as e:
            raise RuntimeError(e) from e

    async def retrieve_single_patient(
        self,
        therapist_id: str,
        patient_id: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                fields=["*"],
                filters={
                    "id": patient_id,
                    "is_soft_deleted": False,
                }
            )
            return {} if len(response) == 0 else response[0]
        except Exception as e:
            raise RuntimeError(e) from e

    async def retrieve_patients(
        self,
        therapist_id: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                fields=["*"],
                order_by=("first_name", "desc"),
                filters={
                    "therapist_id": therapist_id,
                    "is_soft_deleted": False,
                }
            )
            return [] if len(response) == 0 else response
        except Exception as e:
            raise RuntimeError(e) from e

    async def add_patient(
        self,
        background_tasks: BackgroundTasks,
        language_code: str,
        filtered_body: dict,
        therapist_id: str,
        session_id: str | None,
        request: Request,
    ) -> str:
        try:
            environment = os.environ.get('ENVIRONMENT')
            payload = {"therapist_id": therapist_id}
            for key, value in filtered_body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.insert(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                payload=payload
            )
            assert type(response) == dict, "Unexpected data type after insert"
            patient_id = response['id']

            is_first_time_patient = filtered_body['onboarding_first_time_patient']
            if is_first_time_patient:
                try:
                    pre_existing_history = filtered_body['pre_existing_history']
                    assert len(pre_existing_history or '') > 0

                    background_tasks.add_task(
                        dependency_container.inject_pinecone_client().insert_preexisting_history_vectors,
                        user_id=therapist_id,
                        patient_id=patient_id,
                        text=pre_existing_history,
                        openai_client=dependency_container.inject_openai_client(),
                        summarize_chunk=self.chartwise_assistant.summarize_chunk
                    )
                except Exception:
                    # If pre_existing_history is not in `filtered_body` or if it's empty, we won't do anything
                    pass

            # Load default question suggestions
            await self._load_default_question_suggestions_for_new_patient(
                language_code=language_code,
                patient_id=patient_id,
                environment=environment,
                therapist_id=therapist_id,
                session_id=session_id,
                request=request,
            )

            # Load default pre-session tray
            gender = None if 'gender' not in filtered_body else filtered_body['gender'].value
            await self._load_default_pre_session_tray_for_new_patient(
                language_code=language_code,
                patient_id=patient_id,
                environment=environment,
                therapist_id=therapist_id,
                session_id=session_id,
                patient_first_name=filtered_body['first_name'],
                patient_gender=gender,
                is_first_time_patient=is_first_time_patient,
                request=request,
            )
            return patient_id
        except Exception as e:
            raise RuntimeError(e) from e

    async def update_patient(
        self,
        therapist_id: str,
        filtered_body: dict,
        background_tasks: BackgroundTasks,
        request: Request,
    ):
        aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
        patient_query = await aws_db_client.select(
            user_id=therapist_id,
            request=request,
            fields=["*"],
            filters={
                'id': filtered_body['id'],
            },
            table_name=ENCRYPTED_PATIENTS_TABLE_NAME
        )
        assert (0 != len(patient_query)), "There isn't a patient-therapist match with the incoming ids."
        current_pre_existing_history = patient_query[0]['pre_existing_history']

        update_db_payload = {}
        for key, value in filtered_body.items():
            if key == 'id':
                continue
            if isinstance(value, Enum):
                value = value.value
            update_db_payload[key] = value

        update_response = await aws_db_client.update(
            user_id=therapist_id,
            request=request,
            table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
            payload=update_db_payload,
            filters={
                'id': filtered_body['id']
            }
        )
        assert (0 != len(update_response or '')), "Update operation could not be completed"

        if ('pre_existing_history' not in filtered_body
            or filtered_body['pre_existing_history'] == current_pre_existing_history):
            return

        openai_client = dependency_container.inject_openai_client()
        background_tasks.add_task(
            dependency_container.inject_pinecone_client().update_preexisting_history_vectors,
            user_id=therapist_id,
            patient_id=filtered_body['id'],
            text=filtered_body['pre_existing_history'],
            openai_client=openai_client,
            summarize_chunk=self.chartwise_assistant.summarize_chunk
        )

        # New pre-existing history content means we should clear any existing conversation.
        await openai_client.clear_chat_history()

    async def adapt_session_notes_to_soap(
        self,
        session_notes_text: str,
    ) -> str:
        try:
            soap_report = await self.chartwise_assistant.create_soap_report(
                text=session_notes_text,
            )
            return soap_report
        except Exception as e:
            raise RuntimeError(e) from e

    def delete_all_vector_data_for_single_patient(
        self,
        therapist_id: str,
        patient_id: str
    ):
        try:
            pinecone_client = dependency_container.inject_pinecone_client()
            pinecone_client.delete_session_vectors(
                user_id=therapist_id,
                patient_id=patient_id
            )
            pinecone_client.delete_preexisting_history_vectors(
                user_id=therapist_id,
                patient_id=patient_id
            )
        except Exception as e:
            # Index doesn't exist, failing silently. Patient may have been queued for deletion prior to having any
            # data in our vector db
            pass

    def delete_all_vector_data_for_patients(
        self,
        user_id: str,
        patient_ids: list[str]
    ):
        try:
            pinecone_client = dependency_container.inject_pinecone_client()
            for patient_id in patient_ids:
                pinecone_client.delete_session_vectors(
                    user_id=user_id,
                    patient_id=patient_id
                )
        except Exception as e:
            raise RuntimeError(e) from e

    async def query_session(
        self,
        query: AssistantQuery,
        therapist_id: str,
        request: Request,
    ) -> AsyncIterable[str]:
        try:
            # If we don't have cached data about this patient, or if the therapist has
            # asked a question about a different patient, go fetch data.
            if (self.cached_patient_query_data is None
                    or self.cached_patient_query_data.patient_id != query.patient_id):
                aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
                language_code = await general_utilities.get_user_language_code(
                    user_id=therapist_id,
                    aws_db_client=aws_db_client,
                    request=request,
                )
                patient_query = await aws_db_client.select(
                    user_id=therapist_id,
                    request=request,
                    fields=["*"],
                    filters={
                        'id': query.patient_id,
                        'therapist_id': therapist_id
                    },
                    table_name=ENCRYPTED_PATIENTS_TABLE_NAME
                )
                assert (0 != len(patient_query)), "There isn't a patient-therapist match with the incoming ids."

                patient_first_name = patient_query[0]['first_name']
                patient_last_name = patient_query[0]['last_name']
                patient_gender = patient_query[0]['gender']
                patient_last_session_date = patient_query[0]['last_session_date']
                self.cached_patient_query_data = CachedPatientQueryData(
                    patient_id=query.patient_id,
                    patient_first_name=patient_first_name,
                    patient_last_name=patient_last_name,
                    patient_gender=patient_gender,
                    last_session_date=patient_last_session_date,
                    response_language_code=language_code
                )
            else:
                # Read cached data
                patient_first_name = self.cached_patient_query_data.patient_first_name
                patient_last_name = self.cached_patient_query_data.patient_last_name
                patient_gender = self.cached_patient_query_data.patient_gender
                language_code = self.cached_patient_query_data.response_language_code
                patient_last_session_date: date | None = self.cached_patient_query_data.last_session_date

            if patient_last_session_date is not None:
                last_session_date_override = PineconeQuerySessionDateOverride(
                    override_type=PineconeQuerySessionDateOverrideType.SINGLE_DATE,
                    output_prefix_override="*** The following data is from the patient's last session with the therapist ***\n",
                    output_suffix_override="*** End of data associated with the patient's last session with the therapist ***",
                    session_date_start=patient_last_session_date.strftime(datetime_handler.DATE_FORMAT)
                )
            else:
                last_session_date_override = None

            async for part in self.chartwise_assistant.query_store(
                user_id=therapist_id,
                patient_id=query.patient_id,
                patient_name=(" ".join([patient_first_name, patient_last_name])),
                patient_gender=patient_gender,
                query_input=query.text,
                request=request,
                response_language_code=language_code,
                last_session_date_override=last_session_date_override
            ):
                yield part
        except Exception as e:
            raise RuntimeError(e) from e

    async def update_question_suggestions(
        self,
        language_code: str,
        therapist_id: str,
        patient_id: str,
        environment: str,
        session_id: str | None,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            patient_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                filters={
                    'therapist_id': therapist_id,
                    'id': patient_id
                }
            )
            assert (0 != len(patient_query)), "There isn't a patient-therapist match with the incoming ids."
            patient_first_name = patient_query[0]['first_name']
            patient_last_name = patient_query[0]['last_name']
            patient_gender = patient_query[0]['gender']
            unique_active_years = patient_query[0]['unique_active_years']

            if 0 == len(unique_active_years):
                # There are no sessions for the patient. Load zero-state question suggestions.
                await self._load_default_question_suggestions_for_new_patient(
                    language_code=language_code,
                    patient_id=patient_id,
                    environment=environment,
                    therapist_id=therapist_id,
                    session_id=session_id,
                    request=request,
                )
                return

            questions_json_schema: ListQuestionSuggestionsSchema = await self.chartwise_assistant.create_question_suggestions(
                language_code=language_code,
                user_id=therapist_id,
                patient_id=patient_id,
                patient_name=(" ".join([patient_first_name, patient_last_name])),
                patient_gender=patient_gender,
                request=request,
            )

            questions_json = questions_json_schema.model_dump_json()
            now_timestamp = datetime.now()

            # Upsert result to DB
            await aws_db_client.upsert(
                user_id=therapist_id,
                request=request,
                payload={
                    "patient_id": patient_id,
                    "last_updated": now_timestamp,
                    "therapist_id": therapist_id,
                    "questions": eval(questions_json)
                },
                table_name=ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
                conflict_columns=["patient_id"],
            )
        except Exception as e:
            eng_alert = EngineeringAlert(
                description="Updating the question suggestions failed",
                session_id=session_id,
                environment=environment,
                exception=e,
                therapist_id=therapist_id,
                patient_id=patient_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def update_presession_tray(
        self,
        therapist_id: str,
        patient_id: str,
        environment: str,
        session_id: str | None,
        language_code: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            patient_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': therapist_id,
                    'id': patient_id
                },
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME
            )
            assert (0 != len(patient_query)), "There isn't a patient-therapist match with the incoming ids."
            patient_first_name = patient_query[0]['first_name']
            patient_gender = patient_query[0]['gender']
            session_count = patient_query[0]['total_sessions']
            unique_active_years = patient_query[0]['unique_active_years']

            if 0 == len(unique_active_years):
                # There are no sessions for the patient. Load zero-state pre-session tray.
                await self._load_default_pre_session_tray_for_new_patient(
                    language_code=language_code,
                    patient_id=patient_id,
                    environment=environment,
                    therapist_id=therapist_id,
                    session_id=session_id,
                    patient_first_name=patient_first_name,
                    patient_gender=patient_gender,
                    is_first_time_patient=patient_query[0]['onboarding_first_time_patient'],
                    request=request,
                )
                return

            therapist_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                filters={
                    "id": therapist_id
                },
                table_name="therapists"
            )
            assert (0 != len(therapist_query)), "Error caught when trying to find data associated to therapist ID"
            therapist_name = therapist_query[0]['first_name']
            language_code = therapist_query[0]['language_preference']
            therapist_gender = therapist_query[0]['gender']

            briefing = await self.chartwise_assistant.create_briefing(
                user_id=therapist_id,
                patient_id=patient_id,
                language_code=language_code,
                patient_name=patient_first_name,
                patient_gender=patient_gender,
                therapist_name=therapist_name,
                therapist_gender=therapist_gender,
                session_count=session_count,
                request=request,
            )

            # Upsert result to DB
            now_timestamp = datetime.now()
            await aws_db_client.upsert(
                user_id=therapist_id,
                request=request,
                payload={
                    "last_updated": now_timestamp,
                    "patient_id": patient_id,
                    "therapist_id": therapist_id,
                    "briefing": briefing
                },
                conflict_columns=["patient_id"],
                table_name=ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME
            )
        except Exception as e:
            eng_alert = EngineeringAlert(
                description="Updating the presession tray failed",
                session_id=session_id,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                patient_id=patient_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def update_patient_recent_topics(
        self,
        language_code: str,
        therapist_id: str,
        patient_id: str,
        environment: str,
        session_id: str | None,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            patient_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': therapist_id,
                    'id': patient_id
                },
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME
            )
            assert (0 != len(patient_query)), "There isn't a patient-therapist match with the incoming ids."
            patient_first_name = patient_query[0]['first_name']
            patient_last_name = patient_query[0]['last_name']
            patient_gender = patient_query[0]['gender']
            patient_full_name = (" ".join([patient_first_name, patient_last_name]))
            unique_active_years = patient_query[0]["unique_active_years"]

            if 0 == len(unique_active_years):
                # There are no sessions for the patient. Clear out recent topics data.
                await aws_db_client.delete(
                    user_id=therapist_id,
                    request=request,
                    table_name=ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
                    filters={
                        "patient_id": patient_id
                    }
                )
                return

            # There are sessions associated with the patient. Regenerate recent topics.
            recent_topics_schema: ListRecentTopicsSchema = await self.chartwise_assistant.fetch_recent_topics(
                language_code=language_code,
                user_id=therapist_id,
                patient_id=patient_id,
                patient_name=patient_full_name,
                patient_gender=patient_gender,
                request=request,
            )

            topics_insights = await self.chartwise_assistant.generate_recent_topics_insights(
                recent_topics=recent_topics_schema,
                user_id=therapist_id,
                patient_id=patient_id,
                language_code=language_code,
                patient_name=patient_first_name,
                patient_gender=patient_gender,
                request=request,
            )

            recent_topics_json = recent_topics_schema.model_dump_json()
            now_timestamp = datetime.now()

            # Upsert result to DB
            await aws_db_client.upsert(
                user_id=therapist_id,
                request=request,
                payload={
                    "last_updated": now_timestamp,
                    "insights": topics_insights,
                    "patient_id": patient_id,
                    "therapist_id": therapist_id,
                    "topics": eval(recent_topics_json)
                },
                conflict_columns=["patient_id"],
                table_name=ENCRYPTED_PATIENT_TOPICS_TABLE_NAME
            )
        except Exception as e:
            eng_alert = EngineeringAlert(
                description="Updating the recent topics failed",
                session_id=session_id,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                patient_id=patient_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def generate_attendance_insights(
        self,
        language_code: str,
        therapist_id: str,
        patient_id: str,
        session_id: str | None,
        environment: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            patient_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': therapist_id,
                    'id': patient_id
                },
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME
            )
            assert (0 != len(patient_query)), "There isn't a patient-therapist match with the incoming ids."
            patient_first_name = patient_query[0]['first_name']
            patient_gender = patient_query[0]['gender']
            unique_active_years = patient_query[0]['unique_active_years']

            if 0 == len(unique_active_years):
                # There are no sessions for the patient. Clear out attendance insights data.
                await aws_db_client.delete(
                    user_id=therapist_id,
                    request=request,
                    table_name=ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
                    filters={
                        "patient_id": patient_id
                    }
                )
                return

            attendance_insights = await self.chartwise_assistant.generate_attendance_insights(
                therapist_id=therapist_id,
                patient_id=patient_id,
                patient_gender=patient_gender,
                patient_name=patient_first_name,
                language_code=language_code,
                request=request,
            )

            # Upsert result to DB
            now_timestamp = datetime.now()
            await aws_db_client.upsert(
                user_id=therapist_id,
                request=request,
                payload={
                    "last_updated": now_timestamp,
                    "insights": attendance_insights,
                    "patient_id": patient_id,
                    "therapist_id": therapist_id
                },
                conflict_columns=["patient_id"],
                table_name=ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME
            )

        except Exception as e:
            eng_alert = EngineeringAlert(
                description="Updating the attendance insights failed",
                session_id=session_id,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                patient_id=patient_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def update_patient_metrics_after_session_report_operation(
        self,
        patient_id: str,
        environment: str,
        therapist_id: str,
        session_id: str | None,
        operation: SessionCrudOperation,
        request: Request,
        session_date: date | None = None
    ):
        try:
            # Fetch patient last session date and total session count
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            patient_session_notes_data = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                filters={
                    "patient_id": patient_id,
                    "is_soft_deleted": False,
                },
                order_by=("session_date", "desc")
            )
            total_session_count = len(patient_session_notes_data)
            patient_last_session_date: date | None = (
                None if total_session_count == 0
                else patient_session_notes_data[0]['session_date']
            )

            unique_active_years: list[str] = await self.get_patient_active_session_years(
                therapist_id=therapist_id,
                patient_id=patient_id,
                request=request,
            )

            # New value for last_session_date will be the most recent session we already found
            if operation == SessionCrudOperation.DELETE_COMPLETED:
                await aws_db_client.update(
                    user_id=therapist_id,
                    request=request,
                    table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                    payload={
                        "last_session_date": patient_last_session_date,
                        "total_sessions": total_session_count,
                        "unique_active_years": unique_active_years
                    },
                    filters={
                        'id': patient_id
                    }
                )
                return

            # The operation is either insert or update.
            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                assert session_date is not None, "Received an invalid session date"
                patient_last_session_date = session_date
            elif session_date is not None:
                patient_last_session_date = max(patient_last_session_date, session_date)

            await aws_db_client.update(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                payload={
                    "last_session_date": patient_last_session_date,
                    "total_sessions": total_session_count,
                    "unique_active_years": unique_active_years,
                },
                filters={
                    'id': patient_id
                }
            )
        except Exception as e:
            eng_alert = EngineeringAlert(
                description="Updating the patient's \"total session count\" and \"last sesion date\" failed",
                session_id=session_id,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                patient_id=patient_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def get_patient_active_session_years(
        self,
        therapist_id: str,
        patient_id: str,
        request: Request,
    ) -> list[str]:
        aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
        session_dates = await aws_db_client.select(
            user_id=therapist_id,
            request=request,
            fields=["session_date"],
            filters={
                "patient_id": patient_id,
                "is_soft_deleted": False,
            },
            table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME
        )

        unique_active_years: Set[str] = {
            str(entry["session_date"].year) for entry in session_dates if entry["session_date"]
        }

        return sorted(unique_active_years)

    async def default_streaming_error_message(
        self,
        user_id: str,
        request: Request
    ):
        if self.cached_patient_query_data is None:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client,
                request=request,
            )
        else:
            language_code = self.cached_patient_query_data.response_language_code

        if language_code.startswith('es'):
            # Spanish
            return ("Parece que hay un problema que me está impidiendo poder responder tu pregunta. "
                    "Estamos trabajando en ello— ¡Vuelve a intentarlo en un momento!")
        elif language_code.startswith('en'):
            # English
            return ("Looks like there's a minor issue that's preventing me from being able to respond your question. "
                    "We're on it— please check back shortly!")
        else:
            raise Exception("Unsupported language code")

    async def retrieve_attendance_insights(
        self,
        therapist_id: str,
        patient_id: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
                fields=["*"],
                filters={
                    "patient_id": patient_id
                }
            )
            return {} if len(response) == 0 else response[0]
        except Exception as e:
            raise RuntimeError(e) from e

    async def retrieve_briefing(
        self,
        therapist_id: str,
        patient_id: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
                fields=["*"],
                filters={
                    "patient_id": patient_id
                }
            )
            return {} if len(response) == 0 else response[0]
        except Exception as e:
            raise RuntimeError(e) from e

    async def retrieve_question_suggestions(
        self,
        therapist_id: str,
        patient_id: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
                fields=["*"],
                filters={
                    "patient_id": patient_id
                }
            )

            if len(response) == 0:
                return []

            # Because we handle pydantic BaseModel objects, when we dump the JSON model,
            # it returns a dict with a redundant string key. We want to get rid of the unnecessary
            # layer of indirection before returning response to the client.
            response[0]['questions'] = response[0]['questions']['questions']
            return response[0]
        except Exception as e:
            raise RuntimeError(e) from e

    async def recent_topics_data(
        self,
        therapist_id: str,
        patient_id: str,
        request: Request,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
                fields=["*"],
                filters={
                    "patient_id": patient_id
                }
            )

            if len(response) == 0:
                return []

            # Because we handle pydantic BaseModel objects, when we dump the JSON model,
            # it returns a dict with a redundant string key. We want to get rid of the unnecessary
            # layer of indirection before returning response to the client.
            response[0]['topics'] = response[0]['topics']['topics']
            return response[0]
        except Exception as e:
            raise RuntimeError(e) from e

    # Private

    async def _insert_vectors_and_generate_insights(
        self,
        session_notes_id: str,
        therapist_id: str,
        patient_id: str,
        notes_text: str,
        session_date: date,
        session_id: str | None,
        language_code: str,
        environment: str,
        background_tasks: BackgroundTasks,
        auth_manager: AuthManager,
        request: Request,
    ):
        # Update session notes entry with minisummary if needed
        if len(notes_text) > 0:
            await self._update_session_notes_with_mini_summary(
                session_notes_id=session_notes_id,
                notes_text=notes_text,
                therapist_id=therapist_id,
                language_code=language_code,
                auth_manager=auth_manager,
                session_id=session_id,
                environment=environment,
                background_tasks=background_tasks,
                request=request,
                patient_id=patient_id,
            )

        vector_ids = await dependency_container.inject_pinecone_client().insert_session_vectors(
            user_id=therapist_id,
            patient_id=patient_id,
            text=notes_text,
            session_report_id=session_notes_id,
            openai_client=dependency_container.inject_openai_client(),
            therapy_session_date=session_date,
            summarize_chunk=self.chartwise_assistant.summarize_chunk
        )

        # Insert vector ids into mapping table for enhancing RAG accuracy.
        aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
        await aws_db_client.batch_insert(
            user_id=therapist_id,
            request=request,
            table_name=VECTORS_SESSION_MAPPINGS_TABLE_NAME,
            payloads=[
                {
                    "id": vector_id,
                    "therapist_id": therapist_id,
                    "patient_id": patient_id,
                    "session_report_id": session_notes_id,
                    "session_date": session_date,
                }
                for vector_id in vector_ids
            ]
        )

        # Update patient metrics around last session date, and total session count AFTER
        # session has already been inserted.
        await self.update_patient_metrics_after_session_report_operation(
            patient_id=patient_id,
            environment=environment,
            therapist_id=therapist_id,
            session_id=session_id,
            operation=SessionCrudOperation.INSERT_COMPLETED,
            session_date=session_date,
            request=request,
        )

        background_tasks.add_task(
            self._generate_metrics_and_insights,
            language_code=language_code,
            therapist_id=therapist_id,
            patient_id=patient_id,
            environment=environment,
            session_id=session_id,
            request=request,
        )

    async def _update_vectors_and_generate_insights(
        self,
        session_notes_id: str,
        therapist_id: str,
        patient_id: str,
        notes_text: str,
        old_session_date: date,
        new_session_date: date,
        session_id: str | None,
        language_code: str,
        environment: str,
        background_tasks: BackgroundTasks,
        auth_manager: AuthManager,
        request: Request,
    ):
        # We only have to generate a new mini_summary if the session text changed.
        if len(notes_text) > 0:
            await self._update_session_notes_with_mini_summary(
                session_notes_id=session_notes_id,
                notes_text=notes_text,
                therapist_id=therapist_id,
                language_code=language_code,
                auth_manager=auth_manager,
                session_id=session_id,
                environment=environment,
                background_tasks=background_tasks,
                request=request,
                patient_id=patient_id,
            )

        await dependency_container.inject_pinecone_client().update_session_vectors(
            user_id=therapist_id,
            patient_id=patient_id,
            text=notes_text,
            old_date=old_session_date,
            new_date=new_session_date,
            session_report_id=session_notes_id,
            openai_client=dependency_container.inject_openai_client(),
            summarize_chunk=self.chartwise_assistant.summarize_chunk
        )

        # If the session date changed, let's proactively recalculate the patient's last_session_date and total_sessions in case
        # the new session date overwrote the patient's last_session_date value.
        await self.update_patient_metrics_after_session_report_operation(
            patient_id=patient_id,
            therapist_id=therapist_id,
            session_id=session_id,
            environment=environment,
            operation=SessionCrudOperation.UPDATE_COMPLETED,
            session_date=new_session_date,
            request=request,
        )

        background_tasks.add_task(
            self._generate_metrics_and_insights,
            language_code=language_code,
            therapist_id=therapist_id,
            patient_id=patient_id,
            environment=environment,
            session_id=session_id,
            request=request,
        )

    async def _delete_vectors_and_generate_insights(
        self,
        therapist_id: str,
        patient_id: str,
        session_date: date,
        session_id: str | None,
        language_code: str,
        environment: str,
        background_tasks: BackgroundTasks,
        request: Request,
    ):
        dependency_container.inject_pinecone_client().delete_session_vectors(
            user_id=therapist_id,
            patient_id=patient_id,
            date=session_date
        )

        # Update patient metrics around last session date, and total session count AFTER
        # session has already been deleted.
        await self.update_patient_metrics_after_session_report_operation(
            patient_id=patient_id,
            therapist_id=therapist_id,
            session_id=session_id,
            environment=environment,
            operation=SessionCrudOperation.DELETE_COMPLETED,
            session_date=None,
            request=request,
        )

        background_tasks.add_task(
            self._generate_metrics_and_insights,
            language_code=language_code,
            therapist_id=therapist_id,
            patient_id=patient_id,
            environment=environment,
            session_id=session_id,
            request=request,
        )

    async def _generate_metrics_and_insights(
        self,
        language_code: str,
        therapist_id: str,
        patient_id: str,
        environment: str,
        session_id: str | None,
        request: Request,
    ):
        # Clean patient query cache
        self.cached_patient_query_data = None

        # Given our chat history may be stale based on the new data, let's clear anything we have
        await dependency_container.inject_openai_client().clear_chat_history()

        # Pinecone uses an eventually-consistent architecture so we need to wait a few minutes before
        # Reading vectors to maximize chance of data freshness
        if environment != "testing":
            await asyncio.sleep(30)

        # Update this patient's recent topics for future fetches.
        await self.update_patient_recent_topics(
            language_code=language_code,
            therapist_id=therapist_id,
            patient_id=patient_id,
            environment=environment,
            session_id=session_id,
            request=request,
        )

        # Update this patient's presession tray for future fetches.
        await self.update_presession_tray(
            therapist_id=therapist_id,
            patient_id=patient_id,
            environment=environment,
            session_id=session_id,
            language_code=language_code,
            request=request,
        )

        # Update this patient's question suggestions for future fetches.
        await self.update_question_suggestions(
            language_code=language_code,
            therapist_id=therapist_id,
            patient_id=patient_id,
            environment=environment,
            session_id=session_id,
            request=request,
        )

        # Update attendance insights
        await self.generate_attendance_insights(
            language_code=language_code,
            therapist_id=therapist_id,
            patient_id=patient_id,
            session_id=session_id,
            environment=environment,
            request=request,
        )

    def _default_question_suggestions_ids_for_new_patient(
        self,
        language_code: str
    ):
        if language_code.startswith('es'):
            # Spanish
            return [
                'question_suggestions_no_data_default_es_1',
                'question_suggestions_no_data_default_es_2'
            ]
        elif language_code.startswith('en'):
            # English
            return [
                'question_suggestions_no_data_default_en_1',
                'question_suggestions_no_data_default_en_2'
            ]
        else:
            raise Exception("Unsupported language code")

    async def _load_default_question_suggestions_for_new_patient(
        self,
        language_code: str,
        patient_id: str,
        therapist_id: str,
        environment: str | None,
        session_id: str | None,
        request: Request,
    ):
        try:
            # Insert default question suggestions for patient without any session data
            default_question_suggestions = self._default_question_suggestions_ids_for_new_patient(language_code)
            aws_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            strings_query = await aws_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                table_name="user_interface_strings",
                filters={
                    "id": default_question_suggestions,
                }
            )
            assert (0 != len(strings_query)), "Did not find any strings data for the current scenario."

            default_question_suggestions = [item['value'] for item in strings_query]
            await aws_client.upsert(
                user_id=therapist_id,
                request=request,
                conflict_columns=["patient_id"],
                table_name=ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
                payload={
                    "patient_id": patient_id,
                    "therapist_id": therapist_id,
                    "last_updated": datetime.now(),
                    "questions": {
                        # We want to leave this extra layer of indirection for consistency due to the
                        # mechanism we have in place for converting structured output into a Pydantic model (used elsewhere)
                        "questions": eval(
                            json.dumps(
                                default_question_suggestions,
                                ensure_ascii=False,
                            )
                        )
                    }
                }
            )
        except Exception as e:
            eng_alert = EngineeringAlert(
                description="Updating the default question suggestions failed",
                session_id=session_id,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                patient_id=patient_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def _load_default_pre_session_tray_for_new_patient(
        self,
        language_code: str,
        patient_id: str,
        therapist_id: str,
        environment: str | None,
        session_id: str | None,
        patient_first_name: str,
        is_first_time_patient: bool,
        request: Request,
        patient_gender: str | None = None,
    ):
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            therapist_data_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name="therapists",
                fields=["first_name"],
                filters={
                    "id": therapist_id
                }
            )
            assert (1 == len(therapist_data_query)), "Did not find any data for the incoming therapist id."
            therapist_first_name = therapist_data_query[0]['first_name']

            therapist_language = general_utilities.map_language_code_to_language(language_code)
            string_query = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name="static_default_briefings",
                fields=["value"],
                filters={
                    "id": therapist_language
                }
            )
            assert (0 != len(string_query)), "Did not find any strings data for the current scenario."

            briefings = json.loads(string_query[0]['value'])['briefings']
            if not 'has_different_pronouns' in briefings or not briefings['has_different_pronouns']:
                default_briefing = (briefings['existing_patient']['value'] if not is_first_time_patient
                                    else briefings['new_patient']['value'])
                formatted_default_briefing = default_briefing.format(
                    user_first_name=therapist_first_name,
                    patient_first_name=patient_first_name
                )
                await aws_db_client.upsert(
                    user_id=therapist_id,
                    request=request,
                    conflict_columns=["patient_id"],
                    table_name=ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
                    payload={
                        "last_updated": datetime.now(),
                        "patient_id": patient_id,
                        "therapist_id": therapist_id,
                        "briefing": eval(
                            json.dumps(
                                formatted_default_briefing,
                                ensure_ascii=False,
                            )
                        )
                    }
                )
                return

            # Select briefing with gender specification for pre-session tray
            default_briefing = (briefings['existing_patient'] if not is_first_time_patient
                                else briefings['new_patient'])

            if patient_gender is not None and patient_gender == "female":
                default_briefing = default_briefing['female_pronouns']['value']
            else:
                default_briefing = default_briefing['male_pronouns']['value']

            formatted_default_briefing = default_briefing.format(
                user_first_name=therapist_first_name,
                patient_first_name=patient_first_name
            )

            await aws_db_client.upsert(
                user_id=therapist_id,
                request=request,
                conflict_columns=["patient_id"],
                table_name=ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
                payload={
                    "patient_id": patient_id,
                    "therapist_id": therapist_id,
                    "last_updated": datetime.now(),
                    "briefing": eval(
                        json.dumps(
                            formatted_default_briefing,
                            ensure_ascii=False
                        )
                    )
                }
            )
        except Exception as e:
            eng_alert = EngineeringAlert(
                description="Loading the default pre-session tray failed",
                session_id=session_id,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                patient_id=patient_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def _update_session_notes_with_mini_summary(
        self,
        session_notes_id: str,
        notes_text: str,
        therapist_id: str,
        language_code: str,
        auth_manager: AuthManager,
        session_id: str | None,
        environment: str,
        background_tasks: BackgroundTasks,
        request: Request,
        patient_id: str,
    ):
        try:
            mini_summary = await self.chartwise_assistant.create_session_mini_summary(
                session_notes=notes_text,
                language_code=language_code,
            )

            await self.update_session(
                therapist_id=therapist_id,
                language_code=language_code,
                environment=environment,
                background_tasks=background_tasks,
                auth_manager=auth_manager,
                filtered_body={
                    "id": session_notes_id,
                    "notes_mini_summary": mini_summary
                },
                session_id=session_id,
                request=request,
            )
        except Exception as e:
            eng_alert = EngineeringAlert(
                description=f"Updating session report {session_notes_id} with a mini summary failed",
                session_id=session_id,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                patient_id=patient_id,
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=eng_alert)
            raise RuntimeError(e) from e

    async def _retrieve_sessions_for_year(
        self,
        therapist_id: str,
        request: Request,
        patient_id: str,
        year: str
    ) -> list[dict]:
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            year_as_int = int(year)
            session_reports_data = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                fields=["*"],
                filters={
                    "patient_id": patient_id,
                    "session_date__gte": date(year_as_int, 1, 1),
                    "session_date__lte": date(year_as_int, 12, 31),
                    "is_soft_deleted": False,
                },
                order_by=("session_date", "desc"),
            )
            return [] if len(session_reports_data) == 0 else session_reports_data
        except Exception as e:
            raise RuntimeError(e) from e

    async def _retrieve_sessions_in_range(
        self,
        request: Request,
        patient_id: str,
        time_range: TimeRange,
        therapist_id: str
    ) -> list[dict]:
        try:
            now = datetime.now()
            days_map = {
                TimeRange.MONTH: 30,
                TimeRange.YEAR: 365,
                TimeRange.FIVE_YEARS: 1825
            }
            start_date = (now - timedelta(days=days_map[time_range]))
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            response_data = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["session_date"],
                filters={
                    "patient_id": patient_id,
                    "session_date__gte": start_date,
                    "session_date__lte": now,
                    "is_soft_deleted": False,
                },
                order_by=("session_date", "desc"),
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
            )

            if len(response_data) == 0:
                return []

            if time_range == TimeRange.MONTH:
                days = [
                    item['session_date'].strftime(datetime_handler.DAY_MONTH_SLASH_FORMAT)
                    for item in response_data
                ]
                day_counter = Counter(days)
                return [{
                    'date': day,
                    'sessions': day_counter[day]
                } for day in day_counter]
            elif time_range == TimeRange.YEAR:
                language_preference = await general_utilities.get_user_language_code(
                    user_id=therapist_id,
                    aws_db_client=aws_db_client,
                    request=request,
                )
                month_names = [
                    datetime_handler.get_month_abbreviated(
                        date_input=item['session_date'],
                        language_code=language_preference
                    ) for item in response_data
                ]
                month_counter = Counter(month_names)
                months_order = datetime_handler.get_last_12_months_abbr(language_code=language_preference)
                return [{
                    'date': month,
                    'sessions': month_counter.get(month, 0)
                } for month in months_order]
            elif time_range == TimeRange.FIVE_YEARS:
                years = [
                    item['session_date'].strftime(datetime_handler.YEAR_FORMAT)
                    for item in response_data
                ]
                year_counter = Counter(years)
                max_year = max(map(int, years))
                year_range = list(map(str, range(max_year - 4, max_year + 1)))
                return [{
                    'date': year,
                    'sessions': year_counter.get(year, 0)
                } for year in year_range]
            else:
                raise ValueError("Untracked time range value")
        except Exception as e:
            raise RuntimeError(e) from e

    async def _retrieve_n_most_recent_sessions(
        self,
        therapist_id: str,
        request: Request,
        patient_id: str,
        most_recent_n: int
    ) -> list[dict]:
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            session_reports_data = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["*"],
                filters={
                    "patient_id": patient_id,
                    "is_soft_deleted": False,
                },
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                limit=most_recent_n,
                order_by=("session_date", "desc")
            )
            return [] if len(session_reports_data) == 0 else session_reports_data
        except Exception as e:
            raise RuntimeError(e) from e
