import asyncio, json

from celery import shared_task
from datetime import datetime
from enum import Enum
from fastapi import BackgroundTasks
from pydantic import BaseModel
from typing import AsyncIterable, Optional

from ..dependencies.dependency_container import dependency_container
from ..dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager
from ..internal.internal_alert import EngineeringAlert
from ..internal.schemas import Gender, SessionUploadStatus
from ..internal.utilities import datetime_handler, general_utilities
from ..vectors.chartwise_assistant import ChartWiseAssistant

class AssistantQuery(BaseModel):
    patient_id: str
    text: str

class SessionCrudOperation(Enum):
    INSERT_COMPLETED = "insert_completed"
    UPDATE_COMPLETED = "update_completed"
    DELETE_COMPLETED = "delete_completed"

class PatientConsentmentChannel(Enum):
    UNDEFINED = "undefined"
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
    birth_date: Optional[str] = None
    pre_existing_history: Optional[str] = None
    gender: Optional[Gender] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    consentment_channel: Optional[PatientConsentmentChannel] = None

class PatientUpdatePayload(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[str] = None
    pre_existing_history: Optional[str] = None
    gender: Optional[Gender] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    consentment_channel: Optional[PatientConsentmentChannel] = None

class SessionNotesInsert(BaseModel):
    patient_id: str
    notes_text: str
    session_date: str

class SessionNotesUpdate(BaseModel):
    id: str
    notes_text: Optional[str] = None
    session_date: Optional[str] = None
    diarization: Optional[str] = None

class CachedPatientQueryData:
    def __init__(self,
                 patient_id: str,
                 patient_first_name: str,
                 patient_last_name: str,
                 response_language_code: str,
                 patient_gender: Optional[str] = None,
                 last_session_date: Optional[str] = None):
        self.patient_id = patient_id
        self.patient_first_name = patient_first_name
        self.patient_last_name = patient_last_name
        self.patient_gender = patient_gender
        self.last_session_date = last_session_date
        self.response_language_code = response_language_code

class AssistantManager:

    cached_patient_query_data: CachedPatientQueryData = None

    def __init__(self):
        self.chartwise_assistant = ChartWiseAssistant()

    async def process_new_session_data(self,
                                       environment: str,
                                       language_code: str,
                                       background_tasks: BackgroundTasks,
                                       auth_manager: AuthManager,
                                       patient_id: str,
                                       notes_text: str,
                                       session_date: str,
                                       source: SessionNotesSource,
                                       session_id: str,
                                       therapist_id: str,
                                       supabase_client: SupabaseBaseClass,
                                       email_manager: EmailManager,
                                       diarization: str = None) -> str:
        try:
            assert source == SessionNotesSource.MANUAL_INPUT, f"Unexpected SessionNotesSource value \"{source.value}\""
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            insert_payload = {
                "notes_text": notes_text,
                "notes_mini_summary": "-",
                "session_date": session_date,
                "patient_id": patient_id,
                "source": source.value,
                "last_updated": now_timestamp,
                "therapist_id": therapist_id,
                "processing_status": SessionUploadStatus.SUCCESS.value
            }

            if len(diarization or '') > 0:
                insert_payload['diarization'] = diarization

            insert_result = supabase_client.insert(table_name="session_reports",
                                                   payload=insert_payload)
            session_notes_id = insert_result.dict()['data'][0]['id']

            # Upload vector embeddings and generate insights
            background_tasks.add_task(self._insert_vectors_and_generate_insights,
                                      session_notes_id,
                                      therapist_id,
                                      patient_id,
                                      notes_text,
                                      session_date,
                                      session_id,
                                      language_code,
                                      environment,
                                      background_tasks,
                                      auth_manager,
                                      supabase_client,
                                      email_manager)
            return session_notes_id
        except Exception as e:
            raise Exception(e)

    async def update_session(self,
                             language_code: str,
                             environment: str,
                             background_tasks: BackgroundTasks,
                             auth_manager: AuthManager,
                             filtered_body: dict,
                             session_id: str,
                             supabase_client: SupabaseBaseClass,
                             email_manager: EmailManager):
        try:
            session_notes_id = filtered_body['id']
            report_query = supabase_client.select(fields="*",
                                                  table_name="session_reports",
                                                  filters={
                                                      'id': session_notes_id
                                                  })
            assert (0 != len((report_query).data)), "There isn't a match with the incoming session data."
            report_query_data = report_query.dict()['data'][0]
            patient_id = report_query_data['patient_id']
            therapist_id = report_query_data['therapist_id']
            current_session_text = report_query_data['notes_text']
            current_session_date = report_query_data['session_date']
            current_session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(incoming_date=current_session_date,
                                                                                                incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
            session_text_changed = 'notes_text' in filtered_body and filtered_body['notes_text'] != current_session_text
            session_date_changed = 'session_date' in filtered_body and filtered_body['session_date'] != current_session_date_formatted

            # Start populating payload for updating session.
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            session_update_payload = {
                "last_updated": now_timestamp
            }
            for key, value in filtered_body.items():
                if key == 'id':
                    continue
                if isinstance(value, Enum):
                    value = value.value
                session_update_payload[key] = value

            session_update_response = supabase_client.update(table_name="session_reports",
                                                             payload=session_update_payload,
                                                             filters={
                                                                 'id': session_notes_id
                                                             })
            assert (0 != len((session_update_response).data)), "Update operation could not be completed"

            # Update the session vectors if needed
            if session_date_changed or session_text_changed:
                background_tasks.add_task(self._update_vectors_and_generate_insights,
                                          session_notes_id,
                                          therapist_id,
                                          patient_id,
                                          filtered_body.get('notes_text', current_session_text),
                                          current_session_date_formatted,
                                          filtered_body.get('session_date', current_session_date_formatted),
                                          session_id,
                                          language_code,
                                          environment,
                                          background_tasks,
                                          auth_manager,
                                          supabase_client,
                                          email_manager)
        except Exception as e:
            raise Exception(e)

    async def delete_session(self,
                             language_code: str,
                             email_manager: EmailManager,
                             environment: str,
                             session_id: str,
                             background_tasks: BackgroundTasks,
                             therapist_id: str,
                             session_report_id: str,
                             supabase_client: SupabaseBaseClass):
        try:
            # Delete the session notes from Supabase
            delete_result = supabase_client.delete(table_name="session_reports",
                                                   filters={
                                                       'id': session_report_id
                                                   })
            delete_result_data = delete_result.dict()['data']
            assert len(delete_result_data) > 0, "No session found with the incoming session_report_id"
            delete_result_data = delete_result_data[0]

            therapist_id = delete_result_data['therapist_id']
            patient_id = delete_result_data['patient_id']
            session_date = delete_result_data['session_date']

            # Delete vector embeddings
            session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(incoming_date=session_date,
                                                                                        incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
            background_tasks.add_task(self._delete_vectors_and_generate_insights,
                                      therapist_id,
                                      patient_id,
                                      session_date_formatted,
                                      session_id,
                                      language_code,
                                      environment,
                                      background_tasks,
                                      email_manager,
                                      supabase_client)
        except Exception as e:
            raise Exception(e)

    async def add_patient(self,
                          background_tasks: BackgroundTasks,
                          language_code: str,
                          filtered_body: dict,
                          therapist_id: str,
                          session_id: str,
                          supabase_client: SupabaseBaseClass,
                          email_manager: EmailManager) -> str:
        try:
            payload = {"therapist_id": therapist_id}
            for key, value in filtered_body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            response = supabase_client.insert(table_name="patients", payload=payload)
            patient_id = response.dict()['data'][0]['id']

            if 'pre_existing_history' in filtered_body and len(filtered_body['pre_existing_history'] or '') > 0:
                background_tasks.add_task(dependency_container.inject_pinecone_client().insert_preexisting_history_vectors,
                                          session_id,
                                          therapist_id,
                                          patient_id,
                                          filtered_body['pre_existing_history'],
                                          dependency_container.inject_openai_client(),
                                          self.chartwise_assistant.summarize_chunk)

            # Load default question suggestions in a background thread
            await self._load_default_question_suggestions_for_new_patient(supabase_client=supabase_client,
                                                                          language_code=language_code,
                                                                          patient_id=patient_id,
                                                                          therapist_id=therapist_id,
                                                                          email_manager=email_manager,
                                                                          session_id=session_id)

            # Load default pre-session tray
            has_preexisting_history = ('pre_existing_history' in filtered_body)
            gender = None if 'gender' not in filtered_body else filtered_body['gender'].value
            await self._load_default_pre_session_tray_for_new_patient(language_code=language_code,
                                                                      patient_id=patient_id,
                                                                      therapist_id=therapist_id,
                                                                      email_manager=email_manager,
                                                                      session_id=session_id,
                                                                      supabase_client=supabase_client,
                                                                      has_preexisting_history=has_preexisting_history,
                                                                      patient_first_name=filtered_body['first_name'],
                                                                      patient_gender=gender)
            return patient_id
        except Exception as e:
            raise Exception(e)

    async def update_patient(self,
                             auth_manager: AuthManager,
                             filtered_body: dict,
                             session_id: str,
                             background_tasks: BackgroundTasks,
                             supabase_client: SupabaseBaseClass):
        patient_query = supabase_client.select(fields="*",
                                               filters={
                                                   'id': filtered_body['id'],
                                               },
                                               table_name="patients")
        assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
        patient_query_data = patient_query.dict()['data'][0]
        current_pre_existing_history = patient_query_data['pre_existing_history']
        therapist_id = patient_query_data['therapist_id']

        update_db_payload = {}
        for key, value in filtered_body.items():
            if key == 'id':
                continue
            if isinstance(value, Enum):
                value = value.value
            update_db_payload[key] = value

        update_response = supabase_client.update(table_name="patients",
                                                 payload=update_db_payload,
                                                 filters={
                                                     'id': filtered_body['id']
                                                 })
        assert (0 != len((update_response).data)), "Update operation could not be completed"

        if ('pre_existing_history' not in filtered_body
            or filtered_body['pre_existing_history'] == current_pre_existing_history):
            return

        openai_client = dependency_container.inject_openai_client()
        background_tasks.add_task(dependency_container.inject_pinecone_client().update_preexisting_history_vectors,
                                  session_id,
                                  therapist_id,
                                  filtered_body['id'],
                                  filtered_body['pre_existing_history'],
                                  openai_client,
                                  self.chartwise_assistant.summarize_chunk)

        # New pre-existing history content means we should clear any existing conversation.
        await openai_client.clear_chat_history()

    async def adapt_session_notes_to_soap(self,
                                          auth_manager: AuthManager,
                                          therapist_id: str,
                                          session_notes_text: str,
                                          session_id: str) -> str:
        try:
            soap_report = await self.chartwise_assistant.create_soap_report(text=session_notes_text,
                                                                            therapist_id=therapist_id,
                                                                            session_id=session_id)
            return soap_report
        except Exception as e:
            raise Exception(e)

    def delete_all_data_for_patient(self,
                                    therapist_id: str,
                                    patient_id: str):
        try:
            pinecone_client = dependency_container.inject_pinecone_client()
            pinecone_client.delete_session_vectors(user_id=therapist_id, patient_id=patient_id)
            pinecone_client.delete_preexisting_history_vectors(user_id=therapist_id,
                                                               patient_id=patient_id)
        except Exception as e:
            # Index doesn't exist, failing silently. Patient may have been queued for deletion prior to having any
            # data in our vector db
            pass

    def delete_all_sessions_for_therapist(self,
                                          user_id: str,
                                          patient_ids: list[str]):
        try:
            pinecone_client = dependency_container.inject_pinecone_client()
            for patient_id in patient_ids:
                pinecone_client.delete_session_vectors(user_id=user_id,
                                                       patient_id=patient_id)
        except Exception as e:
            raise Exception(e)

    async def query_session(self,
                            query: AssistantQuery,
                            therapist_id: str,
                            session_id: str,
                            environment: str,
                            supabase_client: SupabaseBaseClass) -> AsyncIterable[str]:
        try:
            # If we don't have cached data about this patient, or if the therapist has
            # asked a question about a different patient, go fetch data.
            if (self.cached_patient_query_data is None
                    or self.cached_patient_query_data.patient_id != query.patient_id):
                language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
                patient_query = supabase_client.select(fields="*",
                                                    filters={
                                                        'id': query.patient_id,
                                                        'therapist_id': therapist_id
                                                    },
                                                    table_name="patients")
                patient_therapist_match = (0 != len((patient_query).data))
                assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."

                patient_query_data = patient_query.dict()['data'][0]
                patient_first_name = patient_query_data['first_name']
                patient_last_name = patient_query_data['last_name']
                patient_gender = patient_query_data['gender']
                patient_last_session_date = patient_query_data['last_session_date']
                self.cached_patient_query_data = CachedPatientQueryData(patient_id=query.patient_id,
                                                                        patient_first_name=patient_first_name,
                                                                        patient_last_name=patient_last_name,
                                                                        patient_gender=patient_gender,
                                                                        last_session_date=patient_last_session_date,
                                                                        response_language_code=language_code)
            else:
                # Read cached data
                patient_first_name = self.cached_patient_query_data.patient_first_name
                patient_last_name = self.cached_patient_query_data.patient_last_name
                patient_gender = self.cached_patient_query_data.patient_gender
                patient_last_session_date = self.cached_patient_query_data.last_session_date
                language_code = self.cached_patient_query_data.response_language_code

            if len(patient_last_session_date or '') > 0:
                session_date_override = PineconeQuerySessionDateOverride(output_prefix_override="*** The following data is from the patient's last session with the therapist ***\n",
                                                                         output_suffix_override="*** End of data associated with the patient's last session with the therapist ***",
                                                                         session_date=patient_last_session_date)
            else:
                session_date_override = None

            async for part in self.chartwise_assistant.query_store(user_id=therapist_id,
                                                                   patient_id=query.patient_id,
                                                                   patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                   patient_gender=patient_gender,
                                                                   query_input=query.text,
                                                                   response_language_code=language_code,
                                                                   session_id=session_id,
                                                                   environment=environment,
                                                                   session_date_override=session_date_override):
                yield part
        except Exception as e:
            raise Exception(e)

    async def update_question_suggestions(self,
                                          language_code: str,
                                          therapist_id: str,
                                          patient_id: str,
                                          environment: str,
                                          session_id: str,
                                          supabase_client: SupabaseBaseClass,
                                          email_manager: EmailManager):
        try:
            patient_query = supabase_client.select(fields="*",
                                                   table_name="patients",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   })
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
            patient_query_data = patient_query.dict()['data'][0]
            patient_first_name = patient_query_data['first_name']
            patient_last_name = patient_query_data['last_name']
            patient_gender = patient_query_data['gender']

            questions_json = await self.chartwise_assistant.create_question_suggestions(language_code=language_code,
                                                                                        session_id=session_id,
                                                                                        user_id=therapist_id,
                                                                                        patient_id=patient_id,
                                                                                        environment=environment,
                                                                                        supabase_client=supabase_client,
                                                                                        patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                                        patient_gender=patient_gender)
            assert 'questions' in questions_json, "Missing json key for question suggestions response. Please try again"

            question_suggestions_query = supabase_client.select(fields="*",
                                                                filters={
                                                                    'therapist_id': therapist_id,
                                                                    'patient_id': patient_id
                                                                },
                                                                table_name="patient_question_suggestions")

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            if 0 != len((question_suggestions_query).data):
                # Update existing result in Supabase
                supabase_client.update(payload={
                                           "questions": questions_json,
                                           "last_updated": now_timestamp,
                                       },
                                       filters={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                       },
                                       table_name="patient_question_suggestions")
            else:
                # Insert result to Supabase
                supabase_client.insert(payload={
                                           "patient_id": patient_id,
                                           "last_updated": now_timestamp,
                                           "therapist_id": therapist_id,
                                           "questions": questions_json
                                       },
                                       table_name="patient_question_suggestions")
        except Exception as e:
            eng_alert = EngineeringAlert(description="Updating the question suggestions failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)

    async def update_presession_tray(self,
                                     therapist_id: str,
                                     patient_id: str,
                                     environment: str,
                                     session_id: str,
                                     supabase_client: SupabaseBaseClass,
                                     email_manager: EmailManager):
        try:
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
            patient_response_data = patient_query.dict()['data'][0]
            patient_name = patient_response_data['first_name']
            patient_gender = patient_response_data['gender']
            session_count = patient_response_data['total_sessions']

            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         "id": therapist_id
                                                     },
                                                     table_name="therapists")
            therapist_response_data = therapist_query.dict()['data'][0]
            therapist_name = therapist_response_data['first_name']
            language_code = therapist_response_data['language_preference']
            therapist_gender = therapist_response_data['gender']

            briefing = await self.chartwise_assistant.create_briefing(user_id=therapist_id,
                                                                      patient_id=patient_id,
                                                                      environment=environment,
                                                                      language_code=language_code,
                                                                      session_id=session_id,
                                                                      patient_name=patient_name,
                                                                      patient_gender=patient_gender,
                                                                      therapist_name=therapist_name,
                                                                      therapist_gender=therapist_gender,
                                                                      session_count=session_count,
                                                                      supabase_client=supabase_client)

            briefing_query = supabase_client.select(fields="*",
                                                    filters={
                                                        'therapist_id': therapist_id,
                                                        'patient_id': patient_id
                                                    },
                                                    table_name="patient_briefings")

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            if 0 != len((briefing_query).data):
                # Update existing result in Supabase
                supabase_client.update(payload={
                                           "briefing": briefing,
                                           "last_updated": now_timestamp
                                       },
                                       filters={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                       },
                                       table_name="patient_briefings")
            else:
                # Insert result to Supabase
                supabase_client.insert(payload={
                                           "last_updated": now_timestamp,
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                           "briefing": briefing
                                       },
                                       table_name="patient_briefings")
        except Exception as e:
            eng_alert = EngineeringAlert(description="Updating the presession tray failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)

    async def update_patient_recent_topics(self,
                                           language_code: str,
                                           therapist_id: str,
                                           patient_id: str,
                                           environment: str,
                                           session_id: str,
                                           email_manager: EmailManager,
                                           supabase_client: SupabaseBaseClass):
        try:
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
            patient_query_data = patient_query.dict()['data'][0]
            patient_first_name = patient_query_data['first_name']
            patient_last_name = patient_query_data['last_name']
            patient_gender = patient_query_data['gender']
            patient_full_name = (" ".join([patient_first_name, patient_last_name]))

            recent_topics_json = await self.chartwise_assistant.fetch_recent_topics(language_code=language_code,
                                                                                    session_id=session_id,
                                                                                    user_id=therapist_id,
                                                                                    patient_id=patient_id,
                                                                                    environment=environment,
                                                                                    supabase_client=supabase_client,
                                                                                    patient_name=patient_full_name,
                                                                                    patient_gender=patient_gender)
            assert 'topics' in recent_topics_json, "Missing json key for recent topics response. Please try again"

            topics_insights = await self.chartwise_assistant.generate_recent_topics_insights(recent_topics_json=recent_topics_json,
                                                                                                user_id=therapist_id,
                                                                                                patient_id=patient_id,
                                                                                                environment=environment,
                                                                                                language_code=language_code,
                                                                                                session_id=session_id,
                                                                                                patient_name=patient_first_name,
                                                                                                patient_gender=patient_gender,
                                                                                                supabase_client=supabase_client)

            topics_query = supabase_client.select(fields="*",
                                                  filters={
                                                      'therapist_id': therapist_id,
                                                      'patient_id': patient_id
                                                  },
                                                  table_name="patient_topics")

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            if 0 != len((topics_query).data):
                # Update existing result in Supabase
                supabase_client.update(payload={
                                           "last_updated": now_timestamp,
                                           "topics": recent_topics_json,
                                           "insights": topics_insights
                                       },
                                       filters={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                       },
                                       table_name="patient_topics")
            else:
                # Insert result to Supabase
                supabase_client.insert(payload={
                                           "last_updated": now_timestamp,
                                           "insights": topics_insights,
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                           "topics": recent_topics_json
                                       },
                                       table_name="patient_topics")
        except Exception as e:
            eng_alert = EngineeringAlert(description="Updating the recent topics failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)

    async def generate_attendance_insights(self,
                                           language_code: str,
                                           email_manager: EmailManager,
                                           therapist_id: str,
                                           patient_id: str,
                                           session_id: str,
                                           environment: str,
                                           supabase_client: SupabaseBaseClass):
        try:
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
            patient_query_data = patient_query.dict()['data'][0]
            patient_first_name = patient_query_data['first_name']
            patient_gender = patient_query_data['gender']

            attendance_insights = await self.chartwise_assistant.generate_attendance_insights(therapist_id=therapist_id,
                                                                                              patient_id=patient_id,
                                                                                              patient_gender=patient_gender,
                                                                                              patient_name=patient_first_name,
                                                                                              environment=environment,
                                                                                              language_code=language_code,
                                                                                              session_id=session_id,
                                                                                              supabase_client=supabase_client)

            attendance_query = supabase_client.select(fields="*",
                                                      filters={
                                                          'therapist_id': therapist_id,
                                                          'patient_id': patient_id
                                                      },
                                                      table_name="patient_attendance")

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            if 0 != len((attendance_query).data):
                # Update existing result in Supabase
                supabase_client.update(payload={
                                           "last_updated": now_timestamp,
                                           "insights": attendance_insights
                                       },
                                       filters={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                       },
                                       table_name="patient_attendance")
            else:
                # Insert result to Supabase
                supabase_client.insert(payload={
                                           "last_updated": now_timestamp,
                                           "insights": attendance_insights,
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id
                                       },
                                       table_name="patient_attendance")

        except Exception as e:
            eng_alert = EngineeringAlert(description="Updating the attendance insights failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)

    async def update_patient_metrics_after_session_report_operation(self,
                                                                    supabase_client: SupabaseBaseClass,
                                                                    patient_id: str,
                                                                    therapist_id: str,
                                                                    session_id: str,
                                                                    email_manager: EmailManager,
                                                                    operation: SessionCrudOperation,
                                                                    session_date: str = None):
        try:
            # Fetch patient last session date and total session count
            patient_session_notes_response = supabase_client.select(fields="*",
                                                                    table_name="session_reports",
                                                                    filters={
                                                                        "patient_id": patient_id
                                                                    },
                                                                    order_desc_column="session_date")
            patient_session_notes_data = patient_session_notes_response.dict()['data']
            patient_last_session_date = (None if len(patient_session_notes_data) == 0
                                         else patient_session_notes_data[0]['session_date'])
            total_session_count = len(patient_session_notes_data)

            # New value for last_session_date will be the most recent session we already found
            if operation == SessionCrudOperation.DELETE_COMPLETED:
                supabase_client.update(table_name="patients",
                        payload={
                            "last_session_date": patient_last_session_date,
                            "total_sessions": total_session_count,
                        },
                        filters={
                            'id': patient_id
                        })
                return

            # The operation is either insert or update.
            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                assert session_date is not None, "Received an invalid session date"
                patient_last_session_date = session_date
            else:
                formatted_date = datetime_handler.convert_to_date_format_mm_dd_yyyy(incoming_date=patient_last_session_date,
                                                                                    incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
                patient_last_session_date = datetime_handler.retrieve_most_recent_date(first_date=session_date,
                                                                                       first_date_format=datetime_handler.DATE_FORMAT,
                                                                                       second_date=formatted_date,
                                                                                       second_date_format=datetime_handler.DATE_FORMAT)

            supabase_client.update(table_name="patients",
                                   payload={
                                       "last_session_date": patient_last_session_date,
                                       "total_sessions": total_session_count,
                                   },
                                   filters={
                                       'id': patient_id
                                   })
        except Exception as e:
            eng_alert = EngineeringAlert(description="Updating the patient's \"total session count\" and \"last sesion date\" failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)

    def default_streaming_error_message(self,
                                        user_id: str,
                                        supabase_client: SupabaseBaseClass):
        if self.cached_patient_query_data is None:
            language_code = general_utilities.get_user_language_code(user_id=user_id, supabase_client=supabase_client)
        else:
            language_code = self.cached_patient_query_data.response_language_code

        if language_code.startswith('es-'):
            # Spanish
            return ("Parece que hay un problema que me está impidiendo poder responder tu pregunta. "
                    "Estamos trabajando en ello— ¡Vuelve a intentarlo en un momento!")
        elif language_code.startswith('en-'):
            # English
            return ("Looks like there's a minor issue that's preventing me from being able to respond your question. "
                    "We're on it— please check back shortly!")
        else:
            raise Exception("Unsupported language code")

    # Private

    async def _insert_vectors_and_generate_insights(self,
                                                    session_notes_id: str,
                                                    therapist_id: str,
                                                    patient_id: str,
                                                    notes_text: str,
                                                    session_date: str,
                                                    session_id: str,
                                                    language_code: str,
                                                    environment: str,
                                                    background_tasks: BackgroundTasks,
                                                    auth_manager: AuthManager,
                                                    supabase_client: SupabaseBaseClass,
                                                    email_manager: EmailManager):
        # Update session notes entry with minisummary if needed
        if len(notes_text) > 0:
            await self._update_session_notes_with_mini_summary(session_notes_id=session_notes_id,
                                                               notes_text=notes_text,
                                                               therapist_id=therapist_id,
                                                               language_code=language_code,
                                                               auth_manager=auth_manager,
                                                               session_id=session_id,
                                                               environment=environment,
                                                               background_tasks=background_tasks,
                                                               supabase_client=supabase_client,
                                                               patient_id=patient_id,
                                                               email_manager=email_manager)

        await dependency_container.inject_pinecone_client().insert_session_vectors(session_id=session_id,
                                                                                   user_id=therapist_id,
                                                                                   patient_id=patient_id,
                                                                                   text=notes_text,
                                                                                   session_report_id=session_notes_id,
                                                                                   openai_client=dependency_container.inject_openai_client(),
                                                                                   therapy_session_date=session_date,
                                                                                   summarize_chunk=self.chartwise_assistant.summarize_chunk)

        # Update patient metrics around last session date, and total session count AFTER
        # session has already been inserted.
        await self.update_patient_metrics_after_session_report_operation(supabase_client=supabase_client,
                                                                         patient_id=patient_id,
                                                                         therapist_id=therapist_id,
                                                                         session_id=session_id,
                                                                         email_manager=email_manager,
                                                                         operation=SessionCrudOperation.INSERT_COMPLETED,
                                                                         session_date=session_date)

        background_tasks.add_task(self._generate_metrics_and_insights,
                                  language_code,
                                  background_tasks,
                                  therapist_id,
                                  patient_id,
                                  environment,
                                  session_id,
                                  supabase_client,
                                  email_manager)

    async def _update_vectors_and_generate_insights(self,
                                                    session_notes_id: str,
                                                    therapist_id: str,
                                                    patient_id: str,
                                                    notes_text: str,
                                                    old_session_date: str,
                                                    new_session_date: str,
                                                    session_id: str,
                                                    language_code: str,
                                                    environment: str,
                                                    background_tasks: BackgroundTasks,
                                                    auth_manager: AuthManager,
                                                    supabase_client: SupabaseBaseClass,
                                                    email_manager: EmailManager):
        # We only have to generate a new mini_summary if the session text changed.
        if len(notes_text) > 0:
            await self._update_session_notes_with_mini_summary(session_notes_id=session_notes_id,
                                                               notes_text=notes_text,
                                                               therapist_id=therapist_id,
                                                               language_code=language_code,
                                                               auth_manager=auth_manager,
                                                               session_id=session_id,
                                                               environment=environment,
                                                               background_tasks=background_tasks,
                                                               supabase_client=supabase_client,
                                                               patient_id=patient_id,
                                                               email_manager=email_manager)

        await dependency_container.inject_pinecone_client().update_session_vectors(session_id=session_id,
                                                                                   user_id=therapist_id,
                                                                                   patient_id=patient_id,
                                                                                   text=notes_text,
                                                                                   old_date=old_session_date,
                                                                                   new_date=new_session_date,
                                                                                   session_report_id=session_notes_id,
                                                                                   openai_client=dependency_container.inject_openai_client(),
                                                                                   summarize_chunk=self.chartwise_assistant.summarize_chunk)

        # If the session date changed, let's proactively recalculate the patient's last_session_date and total_sessions in case
        # the new session date overwrote the patient's last_session_date value.
        await self.update_patient_metrics_after_session_report_operation(supabase_client=supabase_client,
                                                                         patient_id=patient_id,
                                                                         therapist_id=therapist_id,
                                                                         session_id=session_id,
                                                                         email_manager=email_manager,
                                                                         operation=SessionCrudOperation.UPDATE_COMPLETED,
                                                                         session_date=new_session_date)

        background_tasks.add_task(self._generate_metrics_and_insights,
                                  language_code,
                                  background_tasks,
                                  therapist_id,
                                  patient_id,
                                  environment,
                                  session_id,
                                  supabase_client,
                                  email_manager)

    async def _delete_vectors_and_generate_insights(self,
                                                    therapist_id: str,
                                                    patient_id: str,
                                                    session_date: str,
                                                    session_id: str,
                                                    language_code: str,
                                                    environment: str,
                                                    background_tasks: BackgroundTasks,
                                                    email_manager: EmailManager,
                                                    supabase_client: SupabaseBaseClass):
        dependency_container.inject_pinecone_client().delete_session_vectors(user_id=therapist_id,
                                                                          patient_id=patient_id,
                                                                          date=session_date)

        # Update patient metrics around last session date, and total session count AFTER
        # session has already been deleted.
        await self.update_patient_metrics_after_session_report_operation(supabase_client=supabase_client,
                                                                         patient_id=patient_id,
                                                                         therapist_id=therapist_id,
                                                                         session_id=session_id,
                                                                         email_manager=email_manager,
                                                                         operation=SessionCrudOperation.DELETE_COMPLETED,
                                                                         session_date=None)

        background_tasks.add_task(self._generate_metrics_and_insights,
                                  language_code,
                                  background_tasks,
                                  therapist_id,
                                  patient_id,
                                  environment,
                                  session_id,
                                  supabase_client,
                                  email_manager)

    async def _generate_metrics_and_insights(self,
                                             language_code: str,
                                             background_tasks: BackgroundTasks,
                                             therapist_id: str,
                                             patient_id: str,
                                             environment: str,
                                             session_id: str,
                                             supabase_client: SupabaseBaseClass,
                                             email_manager: EmailManager):
        # Clean patient query cache
        self.cached_patient_query_data = None

        # Given our chat history may be stale based on the new data, let's clear anything we have
        await dependency_container.inject_openai_client().clear_chat_history()

        # Pinecone uses an eventually-consistent architecture so we need to wait a few minutes before
        # Reading vectors to maximize chance of data freshness
        if environment != "testing":
            await asyncio.sleep(30)

        # Update this patient's recent topics for future fetches.
        await self.update_patient_recent_topics(language_code=language_code,
                                                therapist_id=therapist_id,
                                                patient_id=patient_id,
                                                environment=environment,
                                                session_id=session_id,
                                                email_manager=email_manager,
                                                supabase_client=supabase_client)

        # Update this patient's presession tray for future fetches.
        await self.update_presession_tray(therapist_id=therapist_id,
                                          patient_id=patient_id,
                                          environment=environment,
                                          session_id=session_id,
                                          supabase_client=supabase_client,
                                          email_manager=email_manager)

        # Update this patient's question suggestions for future fetches.
        await self.update_question_suggestions(language_code=language_code,
                                               therapist_id=therapist_id,
                                               patient_id=patient_id,
                                               environment=environment,
                                               session_id=session_id,
                                               supabase_client=supabase_client,
                                               email_manager=email_manager)

        # Update attendance insights
        await self.generate_attendance_insights(language_code=language_code,
                                                email_manager=email_manager,
                                                therapist_id=therapist_id,
                                                patient_id=patient_id,
                                                session_id=session_id,
                                                environment=environment,
                                                supabase_client=supabase_client)

    def _default_question_suggestions_ids_for_new_patient(self, language_code: str):
        if language_code.startswith('es-'):
            # Spanish
            return [
                'question_suggestions_no_data_default_es_1',
                'question_suggestions_no_data_default_es_2'
            ]
        elif language_code.startswith('en-'):
            # English
            return [
                'question_suggestions_no_data_default_en_1',
                'question_suggestions_no_data_default_en_2'
            ]
        else:
            raise Exception("Unsupported language code")

    async def _load_default_question_suggestions_for_new_patient(self,
                                                                 supabase_client: SupabaseBaseClass,
                                                                 language_code: str,
                                                                 patient_id: str,
                                                                 therapist_id: str,
                                                                 email_manager: EmailManager,
                                                                 session_id: str):
        try:
            # Insert default question suggestions for patient without any session data
            default_question_suggestions = self._default_question_suggestions_ids_for_new_patient(language_code)
            strings_query = supabase_client.select_either_or_from_column(fields="*",
                                                                         table_name="user_interface_strings",
                                                                         possible_values=default_question_suggestions)
            assert (0 != len((strings_query).data)), "Did not find any strings data for the current scenario."

            default_question_suggestions = [item['value'] for item in strings_query.dict()['data']]
            response_dict = {
                "questions": default_question_suggestions
            }

            supabase_client.insert(table_name="patient_question_suggestions",
                                   payload={
                                       "patient_id": patient_id,
                                       "therapist_id": therapist_id,
                                       "questions": eval(json.dumps(response_dict, ensure_ascii=False))
                                       })
        except Exception as e:
            eng_alert = EngineeringAlert(description="Updating the default question suggestions failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)

    async def _load_default_pre_session_tray_for_new_patient(self,
                                                             language_code: str,
                                                             patient_id: str,
                                                             therapist_id: str,
                                                             email_manager: EmailManager,
                                                             session_id: str,
                                                             supabase_client: SupabaseBaseClass,
                                                             has_preexisting_history: bool,
                                                             patient_first_name: str,
                                                             patient_gender: str = None):
        try:
            therapist_data_query = supabase_client.select(table_name="therapists",
                                                          fields="first_name",
                                                          filters={
                                                              "id": therapist_id
                                                          })
            assert (0 != len((therapist_data_query).data)), "Did not find any data for the incoming therapist id."
            therapist_first_name = therapist_data_query.dict()['data'][0]['first_name']

            therapist_language = general_utilities.map_language_code_to_language(language_code)
            string_query = supabase_client.select(table_name="static_default_briefings",
                                                  fields="value",
                                                  filters={
                                                      "id": therapist_language
                                                  })
            assert (0 != len((string_query).data)), "Did not find any strings data for the current scenario."

            response_value = string_query.dict()['data'][0]['value']
            briefings = response_value['briefings']
            if not 'has_different_pronouns' in briefings or not briefings['has_different_pronouns']:
                default_briefing = (briefings['existing_patient']['value'] if has_preexisting_history
                                    else briefings['new_patient']['value'])
                formatted_default_briefing = default_briefing.format(user_first_name=therapist_first_name,
                                                                     patient_first_name=patient_first_name)
                supabase_client.insert(table_name="patient_briefings",
                                       payload={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                           "briefing": eval(json.dumps(formatted_default_briefing, ensure_ascii=False))
                                           })
                return

            # Select briefing with gender specification for pre-session tray
            default_briefing = (briefings['existing_patient'] if has_preexisting_history
                                else briefings['new_patient'])

            if patient_gender is not None and patient_gender == "female":
                default_briefing = default_briefing['female_pronouns']['value']
            else:
                default_briefing = default_briefing['male_pronouns']['value']

            formatted_default_briefing = default_briefing.format(user_first_name=therapist_first_name,
                                                                 patient_first_name=patient_first_name)
            supabase_client.insert(table_name="patient_briefings",
                                   payload={
                                        "patient_id": patient_id,
                                        "therapist_id": therapist_id,
                                        "briefing": eval(json.dumps(formatted_default_briefing, ensure_ascii=False))
                                    })
        except Exception as e:
            eng_alert = EngineeringAlert(description="Loading the default pre-session tray failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)

    async def _update_session_notes_with_mini_summary(self,
                                                      session_notes_id: str,
                                                      notes_text: str,
                                                      therapist_id: str,
                                                      language_code: str,
                                                      auth_manager: AuthManager,
                                                      session_id: str,
                                                      environment: str,
                                                      background_tasks: BackgroundTasks,
                                                      supabase_client: SupabaseBaseClass,
                                                      patient_id: str,
                                                      email_manager: EmailManager):
        try:
            mini_summary = await self.chartwise_assistant.create_session_mini_summary(session_notes=notes_text,
                                                                                      therapist_id=therapist_id,
                                                                                      language_code=language_code,
                                                                                      session_id=session_id,
                                                                                      patient_id=patient_id)
            await self.update_session(language_code=language_code,
                                      environment=environment,
                                      background_tasks=background_tasks,
                                      auth_manager=auth_manager,
                                      filtered_body={
                                          "id": session_notes_id,
                                          "notes_mini_summary": mini_summary
                                      },
                                      session_id=session_id,
                                      supabase_client=supabase_client,
                                      email_manager=email_manager)
        except Exception as e:
            eng_alert = EngineeringAlert(description=f"Updating session report {session_notes_id} with a mini summary failed",
                                         session_id=session_id,
                                         exception=e,
                                         therapist_id=therapist_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            raise Exception(e)
