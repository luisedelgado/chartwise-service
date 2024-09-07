import json

from datetime import datetime
from enum import Enum

from fastapi import BackgroundTasks
from pydantic import BaseModel
from typing import AsyncIterable, Optional

from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.pinecone_base_class import PineconeBaseClass
from ..dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..managers.auth_manager import AuthManager
from ..internal.logging import Logger
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
                 patient_gender: Optional[str] = None,
                 last_session_date: Optional[str] = None):
        self.patient_id = patient_id
        self.patient_first_name = patient_first_name
        self.patient_last_name = patient_last_name
        self.patient_gender = patient_gender
        self.last_session_date = last_session_date

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
                                       openai_client: OpenAIBaseClass,
                                       supabase_client: SupabaseBaseClass,
                                       pinecone_client: PineconeBaseClass,
                                       logger_worker: Logger,
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

            # Update session notes entry with minisummary
            if len(notes_text) > 0:
                background_tasks.add_task(self._update_session_notes_with_mini_summary,
                                          session_notes_id,
                                          notes_text,
                                          therapist_id,
                                          language_code,
                                          auth_manager,
                                          openai_client,
                                          session_id,
                                          environment,
                                          background_tasks,
                                          logger_worker,
                                          supabase_client,
                                          pinecone_client)

            # Upload vector embeddings
            background_tasks.add_task(pinecone_client.insert_session_vectors,
                                      therapist_id,
                                      patient_id,
                                      notes_text,
                                      session_id,
                                      auth_manager,
                                      openai_client,
                                      session_date)

            # Update patient metrics around last session date, and total session count AFTER
            # session has already been inserted.
            background_tasks.add_task(self.update_patient_metrics_after_session_report_operation,
                                      supabase_client,
                                      patient_id,
                                      therapist_id,
                                      logger_worker,
                                      session_id,
                                      background_tasks,
                                      SessionCrudOperation.INSERT_COMPLETED,
                                      session_date)

            background_tasks.add_task(self.generate_insights_after_session_data_updates,
                                      language_code,
                                      background_tasks,
                                      therapist_id,
                                      patient_id,
                                      auth_manager,
                                      environment,
                                      session_id,
                                      pinecone_client,
                                      openai_client,
                                      supabase_client,
                                      logger_worker)

            return session_notes_id
        except Exception as e:
            raise Exception(e)

    async def update_session(self,
                             language_code: str,
                             logger_worker: Logger,
                             environment: str,
                             background_tasks: BackgroundTasks,
                             auth_manager: AuthManager,
                             filtered_body: dict,
                             session_id: str,
                             openai_client: OpenAIBaseClass,
                             supabase_client: SupabaseBaseClass,
                             pinecone_client: PineconeBaseClass):
        try:
            report_query = supabase_client.select(fields="*",
                                                  table_name="session_reports",
                                                  filters={
                                                      'id': filtered_body['id']
                                                  })
            assert (0 != len((report_query).data)), "There isn't a match with the incoming session data."
            report_query_data = report_query.dict()['data'][0]
            patient_id = report_query_data['patient_id']
            therapist_id = report_query_data['therapist_id']
            current_session_text = report_query_data['notes_text']
            current_session_date = report_query_data['session_date']
            current_session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=current_session_date,
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
                                                                 'id': filtered_body['id']
                                                             })
            assert (0 != len((session_update_response).data)), "Update operation could not be completed"

            # We only have to generate a new mini_summary if the session text changed.
            if session_text_changed and len(filtered_body['notes_text']) > 0:
                background_tasks.add_task(self._update_session_notes_with_mini_summary,
                                          filtered_body['id'],
                                          filtered_body['notes_text'],
                                          therapist_id,
                                          language_code,
                                          auth_manager,
                                          openai_client,
                                          session_id,
                                          environment,
                                          background_tasks,
                                          logger_worker,
                                          supabase_client,
                                          pinecone_client)

            # If the session date changed, let's proactively recalculate the patient's last_session_date and total_sessions in case
            # the new session date overwrote the patient's last_session_date value.
            if session_date_changed:
                background_tasks.add_task(self.update_patient_metrics_after_session_report_operation,
                                          supabase_client,
                                          patient_id,
                                          therapist_id,
                                          logger_worker,
                                          session_id,
                                          background_tasks,
                                          SessionCrudOperation.UPDATE_COMPLETED,
                                          filtered_body['session_date'])

            # Update the session vectors if needed
            if session_date_changed or session_text_changed:
                background_tasks.add_task(pinecone_client.update_session_vectors,
                                          therapist_id,
                                          patient_id,
                                          filtered_body.get('notes_text', current_session_text),
                                          current_session_date_formatted,
                                          filtered_body.get('session_date', current_session_date_formatted),
                                          session_id,
                                          openai_client,
                                          auth_manager)

                background_tasks.add_task(self.generate_insights_after_session_data_updates,
                                        language_code,
                                        background_tasks,
                                        therapist_id,
                                        patient_id,
                                        auth_manager,
                                        environment,
                                        session_id,
                                        pinecone_client,
                                        openai_client,
                                        supabase_client,
                                        logger_worker)
        except Exception as e:
            raise Exception(e)

    async def delete_session(self,
                             language_code: str,
                             auth_manager: AuthManager,
                             environment: str,
                             session_id: str,
                             background_tasks: BackgroundTasks,
                             openai_client: OpenAIBaseClass,
                             therapist_id: str,
                             session_report_id: str,
                             logger_worker: Logger,
                             supabase_client: SupabaseBaseClass,
                             pinecone_client: PineconeBaseClass):
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
            session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=session_date,
                                                                                        incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
            pinecone_client.delete_session_vectors(user_id=therapist_id,
                                                   patient_id=patient_id,
                                                   date=session_date_formatted)

            # Update patient metrics around last session date, and total session count AFTER
            # session has already been deleted.
            background_tasks.add_task(self.update_patient_metrics_after_session_report_operation,
                                      supabase_client,
                                      patient_id,
                                      therapist_id,
                                      logger_worker,
                                      session_id,
                                      background_tasks,
                                      SessionCrudOperation.DELETE_COMPLETED,
                                      None)

            background_tasks.add_task(self.generate_insights_after_session_data_updates,
                                      language_code,
                                      background_tasks,
                                      therapist_id,
                                      patient_id,
                                      auth_manager,
                                      environment,
                                      session_id,
                                      pinecone_client,
                                      openai_client,
                                      supabase_client,
                                      logger_worker)
        except Exception as e:
            raise Exception(e)

    async def add_patient(self,
                          background_tasks: BackgroundTasks,
                          language_code: str,
                          auth_manager: AuthManager,
                          filtered_body: dict,
                          therapist_id: str,
                          session_id: str,
                          logger_worker: Logger,
                          openai_client: OpenAIBaseClass,
                          supabase_client: SupabaseBaseClass,
                          pinecone_client: PineconeBaseClass) -> str:
        try:
            payload = {"therapist_id": therapist_id}
            for key, value in filtered_body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            response = supabase_client.insert(table_name="patients", payload=payload)
            patient_id = response.dict()['data'][0]['id']

            if 'pre_existing_history' in filtered_body and len(filtered_body['pre_existing_history'] or '') > 0:
                background_tasks.add_task(pinecone_client.insert_preexisting_history_vectors,
                                          therapist_id,
                                          patient_id,
                                          filtered_body['pre_existing_history'],
                                          session_id,
                                          openai_client,
                                          auth_manager)

            # Load default question suggestions in a background thread
            background_tasks.add_task(self._load_default_question_suggestions_for_new_patient,
                                      supabase_client,
                                      language_code,
                                      patient_id,
                                      therapist_id,
                                      logger_worker,
                                      background_tasks,
                                      session_id)

            # Load default pre-session tray in a background thread
            has_preexisting_history = ('pre_existing_history' in filtered_body)
            gender = None if 'gender' not in filtered_body else filtered_body['gender'].value
            self._load_default_pre_session_tray_for_new_patient(language_code=language_code,
                                                                patient_id=patient_id,
                                                                therapist_id=therapist_id,
                                                                logger_worker=logger_worker,
                                                                background_tasks=background_tasks,
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
                             openai_client: OpenAIBaseClass,
                             supabase_client: SupabaseBaseClass,
                             pinecone_client: PineconeBaseClass):
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

        await pinecone_client.update_preexisting_history_vectors(user_id=therapist_id,
                                                                 patient_id=filtered_body['id'],
                                                                 text=filtered_body['pre_existing_history'],
                                                                 session_id=session_id,
                                                                 openai_client=openai_client,
                                                                 auth_manager=auth_manager)

        # New pre-existing history content means we should clear any existing conversation.
        await openai_client.clear_chat_history()

    async def adapt_session_notes_to_soap(self,
                                          auth_manager: AuthManager,
                                          openai_client: OpenAIBaseClass,
                                          therapist_id: str,
                                          session_notes_text: str,
                                          session_id: str) -> str:
        try:
            soap_report = await self.chartwise_assistant.create_soap_report(text=session_notes_text,
                                                                            therapist_id=therapist_id,
                                                                            auth_manager=auth_manager,
                                                                            openai_client=openai_client,
                                                                            session_id=session_id)
            return soap_report
        except Exception as e:
            raise Exception(e)

    def delete_all_data_for_patient(self,
                                    pinecone_client: PineconeBaseClass,
                                    therapist_id: str,
                                    patient_id: str):
        try:
            pinecone_client.delete_session_vectors(user_id=therapist_id, patient_id=patient_id)
            pinecone_client.delete_preexisting_history_vectors(user_id=therapist_id,
                                                               patient_id=patient_id)
        except Exception as e:
            # Index doesn't exist, failing silently. Patient may have been queued for deletion prior to having any
            # data in our vector db
            pass

    def delete_all_sessions_for_therapist(self,
                                          user_id: str,
                                          patient_ids: list[str],
                                          pinecone_client: PineconeBaseClass):
        try:
            for patient_id in patient_ids:
                pinecone_client.delete_session_vectors(user_id=user_id,
                                                       patient_id=patient_id)
        except Exception as e:
            raise Exception(e)

    async def query_session(self,
                            language_code: str,
                            auth_manager: AuthManager,
                            query: AssistantQuery,
                            therapist_id: str,
                            session_id: str,
                            api_method: str,
                            environment: str,
                            openai_client: OpenAIBaseClass,
                            pinecone_client: PineconeBaseClass,
                            supabase_client: SupabaseBaseClass) -> AsyncIterable[str]:
        try:
            # If we don't have cached data about this patient, or if the therapist has
            # asked a question about a different patient, go fetch data.
            if (self.cached_patient_query_data is None
                    or self.cached_patient_query_data.patient_id != query.patient_id):
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
                                                                        last_session_date=patient_last_session_date)
            else:
                # Read cached data
                patient_first_name = self.cached_patient_query_data.patient_first_name
                patient_last_name = self.cached_patient_query_data.patient_last_name
                patient_gender = self.cached_patient_query_data.patient_gender
                patient_last_session_date = self.cached_patient_query_data.last_session_date

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
                                                                   method=api_method,
                                                                   environment=environment,
                                                                   auth_manager=auth_manager,
                                                                   openai_client=openai_client,
                                                                   pinecone_client=pinecone_client,
                                                                   session_date_override=session_date_override):
                yield part
        except Exception as e:
            raise Exception(e)

    async def update_question_suggestions(self,
                                          language_code: str,
                                          therapist_id: str,
                                          patient_id: str,
                                          background_tasks: BackgroundTasks,
                                          auth_manager: AuthManager,
                                          environment: str,
                                          session_id: str,
                                          logger_worker: Logger,
                                          openai_client: OpenAIBaseClass,
                                          pinecone_client: PineconeBaseClass,
                                          supabase_client: SupabaseBaseClass):
        try:
            patient_query = supabase_client.select(fields="*",
                                                   table_name="patients",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   })
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
            patient_query_data = patient_query.dict()['data'][0]

            if patient_query_data['total_sessions'] == 0:
                # Return early since there's no data to generate dynamic questions, and
                # we already added default, generic default questions when the patient was added.
                return

            patient_first_name = patient_query_data['first_name']
            patient_last_name = patient_query_data['last_name']
            patient_gender = patient_query_data['gender']

            questions_json = await self.chartwise_assistant.create_question_suggestions(language_code=language_code,
                                                                                        session_id=session_id,
                                                                                        user_id=therapist_id,
                                                                                        patient_id=patient_id,
                                                                                        environment=environment,
                                                                                        auth_manager=auth_manager,
                                                                                        openai_client=openai_client,
                                                                                        supabase_client=supabase_client,
                                                                                        pinecone_client=pinecone_client,
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
            logger_worker.log_error(background_tasks=background_tasks,
                                    description="Updating the question suggestions failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id)
            raise Exception(e)

    async def update_presession_tray(self,
                                     background_tasks: BackgroundTasks,
                                     therapist_id: str,
                                     patient_id: str,
                                     auth_manager: AuthManager,
                                     environment: str,
                                     session_id: str,
                                     pinecone_client: PineconeBaseClass,
                                     openai_client: OpenAIBaseClass,
                                     supabase_client: SupabaseBaseClass,
                                     logger_worker: Logger):
        try:
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
            patient_response_data = patient_query.dict()['data'][0]

            if patient_response_data['total_sessions'] == 0:
                # Return early since there's no data to generate a presession tray, and
                # we already added a default, generic presession tray when the patient was added.
                return

            patient_name = patient_response_data['first_name']
            patient_gender = patient_response_data['gender']
            last_session_date = patient_response_data['last_session_date']
            session_number = 1 + patient_response_data['total_sessions']

            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         "id": therapist_id
                                                     },
                                                     table_name="therapists")
            therapist_response_data = therapist_query.dict()['data'][0]
            therapist_name = therapist_response_data['first_name']
            language_code = therapist_response_data['language_preference']
            therapist_gender = therapist_response_data['gender']

            if len(last_session_date or '') > 0:
                session_date_override = PineconeQuerySessionDateOverride(output_prefix_override="*** The following data is from the patient's last session with the therapist ***\n",
                                                                         output_suffix_override="*** End of data associated with the patient's last session with the therapist ***",
                                                                         session_date=last_session_date)
            else:
                session_date_override = None

            briefing = await self.chartwise_assistant.create_briefing(user_id=therapist_id,
                                                                      patient_id=patient_id,
                                                                      environment=environment,
                                                                      language_code=language_code,
                                                                      session_id=session_id,
                                                                      patient_name=patient_name,
                                                                      patient_gender=patient_gender,
                                                                      therapist_name=therapist_name,
                                                                      therapist_gender=therapist_gender,
                                                                      session_number=session_number,
                                                                      auth_manager=auth_manager,
                                                                      openai_client=openai_client,
                                                                      supabase_client=supabase_client,
                                                                      pinecone_client=pinecone_client,
                                                                      session_date_override=session_date_override)

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
            logger_worker.log_error(background_tasks=background_tasks,
                                    description="Updating the presession tray failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id)
            raise Exception(e)

    async def update_patient_recent_topics(self,
                                           language_code: str,
                                           therapist_id: str,
                                           patient_id: str,
                                           auth_manager: AuthManager,
                                           environment: str,
                                           session_id: str,
                                           background_tasks: BackgroundTasks,
                                           openai_client: OpenAIBaseClass,
                                           pinecone_client: PineconeBaseClass,
                                           supabase_client: SupabaseBaseClass,
                                           logger_worker: Logger):
        try:
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
            patient_query_data = patient_query.dict()['data'][0]

            if patient_query_data['total_sessions'] == 0:
                # Return early since there's no data to generate recent topics dynamically.
                return

            patient_first_name = patient_query_data['first_name']
            patient_last_name = patient_query_data['last_name']
            patient_gender = patient_query_data['gender']
            patient_full_name = (" ".join([patient_first_name, patient_last_name]))

            recent_topics_json = await self.chartwise_assistant.fetch_recent_topics(language_code=language_code,
                                                                                    session_id=session_id,
                                                                                    user_id=therapist_id,
                                                                                    patient_id=patient_id,
                                                                                    environment=environment,
                                                                                    pinecone_client=pinecone_client,
                                                                                    supabase_client=supabase_client,
                                                                                    openai_client=openai_client,
                                                                                    auth_manager=auth_manager,
                                                                                    patient_name=patient_full_name,
                                                                                    patient_gender=patient_gender)
            assert 'topics' in recent_topics_json, "Missing json key for recent topics response. Please try again"

            topics_insights = await self.chartwise_assistant.generate_recent_topics_insights(recent_topics_json=recent_topics_json,
                                                                                             user_id=therapist_id,
                                                                                             patient_id=patient_id,
                                                                                             environment=environment,
                                                                                             language_code=language_code,
                                                                                             session_id=session_id,
                                                                                             patient_name=patient_full_name,
                                                                                             patient_gender=patient_gender,
                                                                                             supabase_client=supabase_client,
                                                                                             openai_client=openai_client,
                                                                                             pinecone_client=pinecone_client,
                                                                                             auth_manager=auth_manager)

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
            logger_worker.log_error(background_tasks=background_tasks,
                                    description="Updating the recent topics failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id)
            raise Exception(e)

    async def generate_attendance_insights(self,
                                           language_code: str,
                                           background_tasks: BackgroundTasks,
                                           therapist_id: str,
                                           patient_id: str,
                                           session_id: str,
                                           environment: str,
                                           auth_manager: AuthManager,
                                           openai_client: OpenAIBaseClass,
                                           supabase_client: SupabaseBaseClass,
                                           logger_worker: Logger):
        try:
            attendance_insights = await self.chartwise_assistant.generate_attendance_insights(therapist_id=therapist_id,
                                                                                              patient_id=patient_id,
                                                                                              environment=environment,
                                                                                              language_code=language_code,
                                                                                              session_id=session_id,
                                                                                              supabase_client=supabase_client,
                                                                                              openai_client=openai_client,
                                                                                              auth_manager=auth_manager)

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
            logger_worker.log_error(background_tasks=background_tasks,
                                    description="Updating the attendance insights failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id)
            raise Exception(e)

    async def generate_insights_after_session_data_updates(self,
                                                           language_code: str,
                                                           background_tasks: BackgroundTasks,
                                                           therapist_id: str,
                                                           patient_id: str,
                                                           auth_manager: AuthManager,
                                                           environment: str,
                                                           session_id: str,
                                                           pinecone_client: PineconeBaseClass,
                                                           openai_client: OpenAIBaseClass,
                                                           supabase_client: SupabaseBaseClass,
                                                           logger_worker: Logger):
        # Clean patient query cache
        self.cached_patient_query_data = None

        # Given our chat history may be stale based on the new data, let's clear anything we have
        await openai_client.clear_chat_history()

        # Update this patient's recent topics for future fetches.
        await self.update_patient_recent_topics(language_code=language_code,
                                                therapist_id=therapist_id,
                                                patient_id=patient_id,
                                                auth_manager=auth_manager,
                                                environment=environment,
                                                session_id=session_id,
                                                background_tasks=background_tasks,
                                                openai_client=openai_client,
                                                pinecone_client=pinecone_client,
                                                supabase_client=supabase_client,
                                                logger_worker=logger_worker)

        # Update this patient's question suggestions for future fetches.
        await self.update_question_suggestions(language_code=language_code,
                                               therapist_id=therapist_id,
                                               patient_id=patient_id,
                                               background_tasks=background_tasks,
                                               auth_manager=auth_manager,
                                               environment=environment,
                                               session_id=session_id,
                                               logger_worker=logger_worker,
                                               openai_client=openai_client,
                                               pinecone_client=pinecone_client,
                                               supabase_client=supabase_client)

        # Update attendance insights
        await self.generate_attendance_insights(language_code=language_code,
                                                background_tasks=background_tasks,
                                                therapist_id=therapist_id,
                                                patient_id=patient_id,
                                                session_id=session_id,
                                                environment=environment,
                                                auth_manager=auth_manager,
                                                openai_client=openai_client,
                                                supabase_client=supabase_client,
                                                logger_worker=logger_worker)

        # Update this patient's presession tray for future fetches.
        await self.update_presession_tray(background_tasks=background_tasks,
                                          therapist_id=therapist_id,
                                          patient_id=patient_id,
                                          auth_manager=auth_manager,
                                          environment=environment,
                                          session_id=session_id,
                                          pinecone_client=pinecone_client,
                                          openai_client=openai_client,
                                          supabase_client=supabase_client,
                                          logger_worker=logger_worker)

    def update_patient_metrics_after_session_report_operation(self,
                                                              supabase_client: SupabaseBaseClass,
                                                              patient_id: str,
                                                              therapist_id: str,
                                                              logger_worker: Logger,
                                                              session_id: str,
                                                              background_tasks: BackgroundTasks,
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

            # The operation is either inser or update.
            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                assert session_date is not None, "Received an invalid session date"
                patient_last_session_date = session_date
            else:
                formatted_date = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=patient_last_session_date,
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
            logger_worker.log_error(background_tasks=background_tasks,
                                    description="Updating the patient's \"total session count\" and \"last sesion date\" failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id)
            raise Exception(e)

    # Private

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

    def _load_default_question_suggestions_for_new_patient(self,
                                                           supabase_client: SupabaseBaseClass,
                                                           language_code: str,
                                                           patient_id: str,
                                                           therapist_id: str,
                                                           logger_worker: Logger,
                                                           background_tasks: BackgroundTasks,
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
            logger_worker.log_error(background_tasks=background_tasks,
                                    description="Updating the default question suggestions failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id)
            raise Exception(e)

    def _load_default_pre_session_tray_for_new_patient(self,
                                                       language_code: str,
                                                       patient_id: str,
                                                       therapist_id: str,
                                                       logger_worker: Logger,
                                                       background_tasks: BackgroundTasks,
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
            logger_worker.log_error(background_tasks=background_tasks,
                                    description="Loading the default pre-session tray failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id)
            raise Exception(e)

    async def _update_session_notes_with_mini_summary(self,
                                                      session_notes_id: str,
                                                      notes_text: str,
                                                      therapist_id: str,
                                                      language_code: str,
                                                      auth_manager: str,
                                                      openai_client: str,
                                                      session_id: str,
                                                      environment: str,
                                                      background_tasks: BackgroundTasks,
                                                      logger_worker: Logger,
                                                      supabase_client: SupabaseBaseClass,
                                                      pinecone_client: PineconeBaseClass):
        try:
            mini_summary = await self.chartwise_assistant.create_session_mini_summary(session_notes=notes_text,
                                                                                      therapist_id=therapist_id,
                                                                                      language_code=language_code,
                                                                                      auth_manager=auth_manager,
                                                                                      openai_client=openai_client,
                                                                                      session_id=session_id)
            await self.update_session(language_code=language_code,
                                      logger_worker=logger_worker,
                                      environment=environment,
                                      background_tasks=background_tasks,
                                      auth_manager=auth_manager,
                                      filtered_body={
                                          "id": session_notes_id,
                                          "notes_mini_summary": mini_summary
                                      },
                                      session_id=session_id,
                                      openai_client=openai_client,
                                      supabase_client=supabase_client,
                                      pinecone_client=pinecone_client)
        except Exception as e:
            logger_worker.log_error(background_tasks=background_tasks,
                                    description=f"Updating session report {session_notes_id} with a mini summary failed",
                                    session_id=session_id,
                                    therapist_id=therapist_id)
            raise Exception(e)
