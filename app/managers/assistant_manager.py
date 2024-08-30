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
from ..internal.schemas import Gender
from ..internal.utilities import datetime_handler
from ..vectors.chartwise_assistant import ChartWiseAssistant

class AssistantQuery(BaseModel):
    patient_id: str
    text: str

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

class AssistantManager:

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
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'id': patient_id,
                                                       'therapist_id': therapist_id
                                                   },
                                                   table_name="patients")
            patient_query_data = patient_query.dict()['data']
            patient_therapist_match = (0 != len(patient_query_data))
            assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."
            patient_query_data = patient_query_data[0]

            if len(notes_text) > 0:
                mini_summary = await self.chartwise_assistant.create_session_mini_summary(session_notes=notes_text,
                                                                                        therapist_id=therapist_id,
                                                                                        language_code=language_code,
                                                                                        auth_manager=auth_manager,
                                                                                        openai_client=openai_client,
                                                                                        session_id=session_id)
            else:
                mini_summary = None

            patient_last_session_date = patient_query_data['last_session_date']

            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
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
                                       "total_sessions": (1 + (patient_query_data['total_sessions'])),
                                   },
                                   filters={
                                       'id': patient_id
                                   })

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            insert_payload = {
                "notes_text": notes_text,
                "notes_mini_summary": mini_summary,
                "session_date": session_date,
                "patient_id": patient_id,
                "source": source.value,
                "last_updated": now_timestamp,
                "therapist_id": therapist_id
            }

            if len(diarization or '') > 0:
                insert_payload['diarization'] = diarization

            insert_result = supabase_client.insert(table_name="session_reports",
                                                   payload=insert_payload)
            session_notes_id = insert_result.dict()['data'][0]['id']

            # Upload vector embeddings
            await pinecone_client.insert_session_vectors(user_id=therapist_id,
                                                         patient_id=patient_id,
                                                         text=notes_text,
                                                         therapy_session_date=session_date,
                                                         openai_client=openai_client,
                                                         auth_manager=auth_manager,
                                                         session_id=session_id)

            await self.generate_insights_after_session_data_updates(language_code=language_code,
                                                                    background_tasks=background_tasks,
                                                                    therapist_id=therapist_id,
                                                                    patient_id=patient_id,
                                                                    auth_manager=auth_manager,
                                                                    environment=environment,
                                                                    session_id=session_id,
                                                                    pinecone_client=pinecone_client,
                                                                    supabase_client=supabase_client,
                                                                    openai_client=openai_client,
                                                                    logger_worker=logger_worker)

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

            # We only have to generate a new mini_summary if the session text changed.
            if session_text_changed and len(filtered_body['notes_text']) > 0:
                session_update_payload['notes_mini_summary'] = await self.chartwise_assistant.create_session_mini_summary(session_notes=filtered_body['notes_text'],
                                                                                                                          therapist_id=therapist_id,
                                                                                                                          language_code=language_code,
                                                                                                                          auth_manager=auth_manager,
                                                                                                                          openai_client=openai_client,
                                                                                                                          session_id=session_id)

            # If the session date changed, let's proactively recalculate the patient's last_session_date and total_sessions in case
            # the new session date overwrote the patient's last_session_date value.
            if session_date_changed:
                patient_query = supabase_client.select(fields="*",
                                                       filters={
                                                           'id': patient_id,
                                                           'therapist_id': therapist_id
                                                       },
                                                       table_name="patients")
                assert (0 != len((patient_query).data)), "Could not fetch the patient's information"
                patient_query_data = patient_query.dict()['data']
                total_sessions = 1 + patient_query_data[0]['total_sessions']

                last_session_date_query = supabase_client.select(fields="*",
                                                                 table_name="session_reports",
                                                                 order_desc_column="session_date",
                                                                 filters={
                                                                     'patient_id': patient_id
                                                                 })
                assert (0 != len((last_session_date_query).data)), "Could not fetch the patient's session reports"
                last_session_date = last_session_date_query.dict()['data'][0]['session_date']

                if last_session_date is None:
                    last_session_date = filtered_body['session_date']
                else:
                    formatted_last_session_date = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=last_session_date,
                                                                                                     incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
                    last_session_date = datetime_handler.retrieve_most_recent_date(first_date=filtered_body['session_date'],
                                                                                   first_date_format=datetime_handler.DATE_FORMAT,
                                                                                   second_date=formatted_last_session_date,
                                                                                   second_date_format=datetime_handler.DATE_FORMAT)

                patient_update_payload = {
                    "last_session_date": last_session_date,
                    "total_sessions": total_sessions
                }
                patient_update_response = supabase_client.update(table_name="patients",
                                                                 payload=patient_update_payload,
                                                                 filters={
                                                                     'id': patient_id
                                                                 })
                assert (0 != len((patient_update_response).data)), "Patient update operation could not be completed"

            session_update_response = supabase_client.update(table_name="session_reports",
                                                             payload=session_update_payload,
                                                             filters={
                                                                 'id': filtered_body['id']
                                                             })
            assert (0 != len((session_update_response).data)), "Update operation could not be completed"

            if session_date_changed or session_text_changed:
                await pinecone_client.update_session_vectors(user_id=therapist_id,
                                                             patient_id=patient_id,
                                                             text=filtered_body.get('notes_text', current_session_text),
                                                             session_id=session_id,
                                                             old_date=current_session_date_formatted,
                                                             new_date=filtered_body.get('session_date', current_session_date_formatted),
                                                             openai_client=openai_client,
                                                             auth_manager=auth_manager)

            await self.generate_insights_after_session_data_updates(language_code=language_code,
                                                                    background_tasks=background_tasks,
                                                                    therapist_id=therapist_id,
                                                                    patient_id=patient_id,
                                                                    auth_manager=auth_manager,
                                                                    environment=environment,
                                                                    session_id=session_id,
                                                                    pinecone_client=pinecone_client,
                                                                    supabase_client=supabase_client,
                                                                    openai_client=openai_client,
                                                                    logger_worker=logger_worker)
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
            # Validate the session report is linked to the therapist id
            report_query = supabase_client.select(fields="*",
                                                  table_name="session_reports",
                                                  filters={
                                                      'id': session_report_id,
                                                      'therapist_id': therapist_id
                                                  })
            assert (0 != len((report_query).data)), "The incoming therapist_id isn't associated with the session_report_id."
            patient_id = report_query.dict()['data'][0]['patient_id']

            # Grab the most recent session date to determine if we'll have to update it
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'id': patient_id,
                                                       'therapist_id': therapist_id
                                                   },
                                                   table_name="patients")
            patient_query_data = patient_query.dict()['data']
            assert len(patient_query_data) > 0, "No patient data found"
            patient_last_session_date = patient_query_data[0]['last_session_date']

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

            # If we deleted the last_session_date we were tracking for the patient, we should update what the new last_session_date is
            if session_date == patient_last_session_date:
                patient_session_notes_response = supabase_client.select(fields="*",
                                                                        table_name="session_reports",
                                                                        filters={
                                                                            "patient_id": patient_id
                                                                        },
                                                                        order_desc_column="session_date")
                patient_session_notes_response_dict = patient_session_notes_response.dict()['data']
                patient_last_session_date = (None if len(patient_session_notes_response_dict) == 0
                                             else patient_session_notes_response_dict[0]['session_date'])

            # Update total_sessions and last_session_date
            supabase_client.update(table_name="patients",
                                   payload={
                                       "total_sessions": (patient_query_data[0]['total_sessions'] - 1),
                                       "last_session_date": patient_last_session_date,
                                   },
                                   filters={
                                       'id': patient_id
                                   })

            # Delete vector embeddings
            session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=session_date,
                                                                                        incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
            pinecone_client.delete_session_vectors(user_id=therapist_id,
                                                   patient_id=patient_id,
                                                   date=session_date_formatted)

            await self.generate_insights_after_session_data_updates(language_code=language_code,
                                                                    background_tasks=background_tasks,
                                                                    therapist_id=therapist_id,
                                                                    patient_id=patient_id,
                                                                    auth_manager=auth_manager,
                                                                    environment=environment,
                                                                    session_id=session_id,
                                                                    logger_worker=logger_worker,
                                                                    pinecone_client=pinecone_client,
                                                                    supabase_client=supabase_client,
                                                                    openai_client=openai_client)
        except Exception as e:
            raise Exception(e)

    async def add_patient(self,
                          language_code: str,
                          auth_manager: AuthManager,
                          filtered_body: dict,
                          therapist_id: str,
                          session_id: str,
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
                await pinecone_client.insert_preexisting_history_vectors(user_id=therapist_id,
                                                                         patient_id=patient_id,
                                                                         text=filtered_body['pre_existing_history'],
                                                                         auth_manager=auth_manager,
                                                                         openai_client=openai_client,
                                                                         session_id=session_id)

            # Insert default question suggestions for patient without any session data
            default_question_suggestions = self._default_question_suggestions_ids_for_new_patient(language_code)
            strings_query = supabase_client.select_either_or_from_column(fields="*",
                                                                         table_name="user_interface_strings",
                                                                         column_name="id",
                                                                         possible_values=default_question_suggestions)
            assert (0 != len((strings_query).data)), "Did not find any strings data for the current scenario."

            default_question_suggestions = [item['value'] for item in strings_query.dict()['data']]
            response_dict = {
                "questions": default_question_suggestions
            }

            supabase_client.insert(table_name="patient_question_suggestions", payload={
                "patient_id": patient_id,
                "therapist_id": therapist_id,
                "questions": eval(json.dumps(response_dict, ensure_ascii=False))
            })

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
            # Confirm that the incoming patient id is assigned to the incoming therapist id.
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
                                    description="Updating the question suggestions in a background task failed",
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
                                     supabase_client: SupabaseBaseClass):
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
            Logger().log_error(background_tasks=background_tasks,
                               description="Updating the presession tray in a background task failed",
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
                                    description="Updating the recent topics in a background task failed",
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
                                    description="Updating the attendance insights in a background task failed",
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

        # Given our chat history may be stale based on the new data, let's clear anything we have
        background_tasks.add_task(openai_client.clear_chat_history)

        # Update this patient's recent topics for future fetches.
        background_tasks.add_task(self.update_patient_recent_topics,
                                  language_code,
                                  therapist_id,
                                  patient_id,
                                  auth_manager,
                                  environment,
                                  session_id,
                                  background_tasks,
                                  openai_client,
                                  pinecone_client,
                                  supabase_client,
                                  logger_worker)

        # Update this patient's question suggestions for future fetches.
        background_tasks.add_task(self.update_question_suggestions,
                                  language_code,
                                  therapist_id,
                                  patient_id,
                                  background_tasks,
                                  auth_manager,
                                  environment,
                                  session_id,
                                  logger_worker,
                                  openai_client,
                                  pinecone_client,
                                  supabase_client)

        # Update attendance insights
        background_tasks.add_task(self.generate_attendance_insights,
                                  language_code,
                                  background_tasks,
                                  therapist_id,
                                  patient_id,
                                  session_id,
                                  environment,
                                  auth_manager,
                                  openai_client,
                                  supabase_client,
                                  logger_worker)

        # Update this patient's presession tray for future fetches.
        background_tasks.add_task(self.update_presession_tray,
                                  background_tasks,
                                  therapist_id,
                                  patient_id,
                                  auth_manager,
                                  environment,
                                  session_id,
                                  pinecone_client,
                                  openai_client,
                                  supabase_client)

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
