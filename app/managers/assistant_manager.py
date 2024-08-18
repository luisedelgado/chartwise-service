from datetime import datetime
from enum import Enum

from fastapi import BackgroundTasks
from pydantic import BaseModel
from typing import AsyncIterable, Optional

from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.pinecone_base_class import PineconeBaseClass
from ..dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.templates import SessionNotesTemplate
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
    client_timezone_identifier: str
    source: SessionNotesSource

class SessionNotesUpdate(BaseModel):
    id: str
    session_date: Optional[str] = None
    client_timezone_identifier: Optional[str] = None
    source: Optional[SessionNotesSource] = None
    diarization: Optional[str] = None
    notes_text: Optional[str] = None

class AssistantManager:

    def __init__(self):
        self.chartwise_assistant = ChartWiseAssistant()

    async def process_new_session_data(self,
                                       environment: str,
                                       background_tasks: BackgroundTasks,
                                       auth_manager: AuthManager,
                                       body: SessionNotesInsert,
                                       session_id: str,
                                       therapist_id: str,
                                       openai_client: OpenAIBaseClass,
                                       supabase_client: SupabaseBaseClass,
                                       pinecone_client: PineconeBaseClass) -> str:
        try:
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'id': body.patient_id,
                                                       'therapist_id': therapist_id
                                                   },
                                                   table_name="patients")
            patient_query_dict = patient_query.dict()
            patient_therapist_match = (0 != len(patient_query_dict['data']))
            assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."

            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         'id': therapist_id
                                                     },
                                                     table_name="therapists")
            assert (0 != len(therapist_query.data))

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            mini_summary = await ChartWiseAssistant().create_session_mini_summary(session_notes=body.notes_text,
                                                                                  therapist_id=therapist_id,
                                                                                  language_code=language_code,
                                                                                  auth_manager=auth_manager,
                                                                                  openai_client=openai_client,
                                                                                  session_id=session_id)

            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                patient_last_session_date = body.session_date
            else:
                formatted_date = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=patient_last_session_date,
                                                                                    incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
                patient_last_session_date = datetime_handler.retrieve_most_recent_date(first_date=body.session_date,
                                                                                       first_date_format=datetime_handler.DATE_FORMAT,
                                                                                       second_date=formatted_date,
                                                                                       second_date_format=datetime_handler.DATE_FORMAT)

            supabase_client.update(table_name="patients",
                                   payload={
                                       "last_session_date": patient_last_session_date,
                                       "total_sessions": (1 + (patient_query_dict['data'][0]['total_sessions'])),
                                   },
                                   filters={
                                       'id': body.patient_id
                                   })

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            insert_result = supabase_client.insert(table_name="session_reports",
                                                   payload={
                                                       "notes_text": body.notes_text,
                                                       "notes_mini_summary": mini_summary,
                                                       "session_date": body.session_date,
                                                       "patient_id": body.patient_id,
                                                       "source": body.source.value,
                                                       "last_updated": now_timestamp,
                                                       "therapist_id": therapist_id
                                                   })
            session_notes_id = insert_result.dict()['data'][0]['id']

            # Upload vector embeddings
            await pinecone_client.insert_session_vectors(index_id=therapist_id,
                                                         namespace=body.patient_id,
                                                         text=body.notes_text,
                                                         therapy_session_date=body.session_date,
                                                         openai_client=openai_client,
                                                         auth_manager=auth_manager,
                                                         session_id=session_id)

            await self.generate_insights_after_session_data_updates(background_tasks=background_tasks,
                                                                    therapist_id=therapist_id,
                                                                    patient_id=body.patient_id,
                                                                    auth_manager=auth_manager,
                                                                    environment=environment,
                                                                    session_id=session_id,
                                                                    pinecone_client=pinecone_client,
                                                                    supabase_client=supabase_client,
                                                                    openai_client=openai_client)

            return session_notes_id
        except Exception as e:
            raise Exception(e)

    async def update_session(self,
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
            report_query_dict = report_query.dict()
            patient_id = report_query_dict['data'][0]['patient_id']
            therapist_id = report_query_dict['data'][0]['therapist_id']
            current_session_text = report_query_dict['data'][0]['notes_text']
            current_session_date = report_query_dict['data'][0]['session_date']
            current_session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=current_session_date,
                                                                                                incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
            session_text_changed = 'notes_text' in filtered_body and filtered_body['notes_text'] != current_session_text
            session_date_changed = 'session_date' in filtered_body and filtered_body['session_date'] != current_session_date_formatted

            # Start populating payload for updating session.
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            payload = {
                "last_updated": now_timestamp
            }
            for key, value in filtered_body.items():
                if key == 'id':
                    continue
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            # We only have to generate a new mini_summary if the session text changed.
            if session_text_changed:
                therapist_query = supabase_client.select(fields="*",
                                                         table_name="therapists",
                                                         filters={
                                                             'id': therapist_id
                                                         })
                assert (0 != len((therapist_query).data)), "Did not find information associated with the therapist."

                language_code = therapist_query.dict()['data'][0]["language_preference"]
                payload['notes_mini_summary'] = await ChartWiseAssistant().create_session_mini_summary(session_notes=filtered_body['notes_text'],
                                                                                                       therapist_id=therapist_id,
                                                                                                       language_code=language_code,
                                                                                                       auth_manager=auth_manager,
                                                                                                       openai_client=openai_client,
                                                                                                       session_id=session_id)

            update_response = supabase_client.update(table_name="session_reports",
                                                     payload=payload,
                                                     filters={
                                                         'id': filtered_body['id']
                                                     })
            assert (0 != len((update_response).data)), "Update operation could not be completed"

            if session_date_changed or session_text_changed:
                await pinecone_client.update_session_vectors(index_id=therapist_id,
                                                             namespace=patient_id,
                                                             text=filtered_body.get('notes_text', current_session_text),
                                                             session_id=session_id,
                                                             old_date=current_session_date_formatted,
                                                             new_date=filtered_body.get('session_date', current_session_date_formatted),
                                                             openai_client=openai_client,
                                                             auth_manager=auth_manager)

            await self.generate_insights_after_session_data_updates(background_tasks=background_tasks,
                                                                    therapist_id=therapist_id,
                                                                    patient_id=patient_id,
                                                                    auth_manager=auth_manager,
                                                                    environment=environment,
                                                                    session_id=session_id,
                                                                    pinecone_client=pinecone_client,
                                                                    supabase_client=supabase_client,
                                                                    openai_client=openai_client)
        except Exception as e:
            raise Exception(e)

    async def delete_session(self,
                             auth_manager: AuthManager,
                             environment: str,
                             session_id: str,
                             background_tasks: BackgroundTasks,
                             openai_client: OpenAIBaseClass,
                             therapist_id: str,
                             session_report_id: str,
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
            patient_query_dict = patient_query.dict()
            assert len(patient_query_dict['data']) > 0, "No patient data found"
            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            # Delete the session notes from Supabase
            delete_result = supabase_client.delete(table_name="session_reports",
                                                   filters={
                                                       'id': session_report_id
                                                   })
            delete_result_dict = delete_result.dict()
            assert len(delete_result_dict['data']) > 0, "No session found with the incoming session_report_id"

            therapist_id = delete_result_dict['data'][0]['therapist_id']
            patient_id = delete_result_dict['data'][0]['patient_id']
            session_date = delete_result_dict['data'][0]['session_date']

            # If we deleted the last_session_date we were tracking for the patient, we should update what the new last_session_date is
            if session_date == patient_last_session_date:
                patient_session_notes_response = supabase_client.select(fields="*",
                                                                        table_name="session_reports",
                                                                        filters={
                                                                            "patient_id": patient_id
                                                                        },
                                                                        order_desc_column="session_date")
                patient_session_notes_response_dict = patient_session_notes_response.dict()
                patient_last_session_date = (None if len(patient_session_notes_response_dict['data']) == 0
                                             else patient_session_notes_response_dict['data'][0]['session_date'])

            # Update total_sessions and last_session_date
            supabase_client.update(table_name="patients",
                                   payload={
                                       "total_sessions": (patient_query_dict['data'][0]['total_sessions'] - 1),
                                       "last_session_date": patient_last_session_date,
                                   },
                                   filters={
                                       'id': patient_id
                                   })

            # Delete vector embeddings
            session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=session_date,
                                                                                        incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
            pinecone_client.delete_session_vectors(index_id=therapist_id,
                                                   namespace=patient_id,
                                                   date=session_date_formatted)

            await self.generate_insights_after_session_data_updates(background_tasks=background_tasks,
                                                                    therapist_id=therapist_id,
                                                                    patient_id=patient_id,
                                                                    auth_manager=auth_manager,
                                                                    environment=environment,
                                                                    session_id=session_id,
                                                                    pinecone_client=pinecone_client,
                                                                    supabase_client=supabase_client,
                                                                    openai_client=openai_client)
        except Exception as e:
            raise Exception(e)

    async def add_patient(self,
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
                await pinecone_client.insert_preexisting_history_vectors(index_id=therapist_id,
                                                                         namespace=patient_id,
                                                                         text=filtered_body['pre_existing_history'],
                                                                         auth_manager=auth_manager,
                                                                         openai_client=openai_client,
                                                                         session_id=session_id)

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
        patient_query_dict = patient_query.dict()
        current_pre_existing_history = patient_query_dict['data'][0]['pre_existing_history']
        therapist_id = patient_query_dict['data'][0]['therapist_id']

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

        await pinecone_client.update_preexisting_history_vectors(index_id=therapist_id,
                                                                 namespace=filtered_body['id'],
                                                                 text=filtered_body['pre_existing_history'],
                                                                 session_id=session_id,
                                                                 openai_client=openai_client,
                                                                 auth_manager=auth_manager)

    async def adapt_session_notes_to_soap(self,
                                          auth_manager: AuthManager,
                                          openai_client: OpenAIBaseClass,
                                          therapist_id: str,
                                          session_notes_text: str,
                                          session_id: str) -> str:
        try:
            soap_report = await ChartWiseAssistant().create_soap_report(text=session_notes_text,
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
            pinecone_client.delete_session_vectors(index_id=therapist_id, namespace=patient_id)
            pinecone_client.delete_preexisting_history_vectors(index_id=therapist_id, namespace=patient_id)
        except Exception as e:
            # Index doesn't exist, failing silently. Patient may have been queued for deletion prior to having any
            # data in our vector db
            pass

    def delete_all_sessions_for_therapist(self,
                                          id: str,
                                          pinecone_client: PineconeBaseClass):
        try:
            pinecone_client.delete_index(id)
        except Exception as e:
            raise Exception(e)

    async def query_session(self,
                            auth_manager: AuthManager,
                            query: AssistantQuery,
                            therapist_id: str,
                            session_id: str,
                            api_method: str,
                            endpoint_name: str,
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

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']
            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            if len(patient_last_session_date or '') > 0:
                session_date_override = PineconeQuerySessionDateOverride(output_prefix_override="*** The following data is from the patient's last session with the therapist ***\n",
                                                                         output_suffix_override="*** End of data associated with the patient's last session with the therapist ***",
                                                                         session_date=patient_last_session_date)
            else:
                session_date_override = None

            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         'id': therapist_id
                                                     },
                                                     table_name="therapists")
            assert (0 != len((therapist_query).data))
            language_code = therapist_query.dict()['data'][0]["language_preference"]

            async for part in self.chartwise_assistant.query_store(index_id=therapist_id,
                                                                   namespace=query.patient_id,
                                                                   patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                   patient_gender=patient_gender,
                                                                   query_input=query.text,
                                                                   response_language_code=language_code,
                                                                   session_id=session_id,
                                                                   endpoint_name=endpoint_name,
                                                                   method=api_method,
                                                                   environment=environment,
                                                                   auth_manager=auth_manager,
                                                                   openai_client=openai_client,
                                                                   pinecone_client=pinecone_client,
                                                                   session_date_override=session_date_override):
                yield part
        except Exception as e:
            raise Exception(e)

    async def fetch_todays_greeting(self,
                                    client_tz_identifier: str,
                                    therapist_id: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    api_method: str,
                                    environment: str,
                                    auth_manager: AuthManager,
                                    openai_client: OpenAIBaseClass,
                                    supabase_client: SupabaseBaseClass) -> str:
        try:
            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         'id': therapist_id
                                                     },
                                                     table_name="therapists")
            assert (0 != len((therapist_query).data)), "No user was found with the incoming id"

            therapist_query_dict = therapist_query.dict()
            addressing_name = therapist_query_dict['data'][0]["first_name"]
            language_code = therapist_query_dict['data'][0]["language_preference"]
            therapist_gender = therapist_query_dict['data'][0]["gender"]
            result = await ChartWiseAssistant().create_greeting(therapist_name=addressing_name,
                                                                therapist_gender=therapist_gender,
                                                                language_code=language_code,
                                                                tz_identifier=client_tz_identifier,
                                                                session_id=session_id,
                                                                endpoint_name=endpoint_name,
                                                                therapist_id=therapist_id,
                                                                method=api_method,
                                                                environment=environment,
                                                                openai_client=openai_client,
                                                                auth_manager=auth_manager)
            return result
        except Exception as e:
            raise Exception(e)

    async def update_question_suggestions(self,
                                          therapist_id: str,
                                          patient_id: str,
                                          background_tasks: BackgroundTasks,
                                          auth_manager: AuthManager,
                                          environment: str,
                                          session_id: str,
                                          openai_client: OpenAIBaseClass,
                                          pinecone_client: PineconeBaseClass,
                                          supabase_client: SupabaseBaseClass):
        try:
            therapist_query = supabase_client.select(fields="*",
                                                     table_name="therapists",
                                                     filters={
                                                         'id': therapist_id
                                                     })
            assert (0 != len((therapist_query).data)), "Did not find any store data for incoming user."

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            patient_query = supabase_client.select(fields="*",
                                                   table_name="patients",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   })
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            questions_json = await ChartWiseAssistant().create_question_suggestions(language_code=language_code,
                                                                                    session_id=session_id,
                                                                                    index_id=therapist_id,
                                                                                    namespace=patient_id,
                                                                                    environment=environment,
                                                                                    auth_manager=auth_manager,
                                                                                    openai_client=openai_client,
                                                                                    pinecone_client=pinecone_client,
                                                                                    supabase_client=supabase_client,
                                                                                    patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                                    patient_gender=patient_gender)
            assert 'questions' in questions_json, "Missing json key for frequent topics response. Please try again"

            question_suggestions_query = supabase_client.select(fields="*",
                                                                filters={
                                                                    'therapist_id': therapist_id,
                                                                    'patient_id': patient_id
                                                                },
                                                                table_name="patient_question_suggestions")
            if 0 != len((question_suggestions_query).data):
                # Update existing result in Supabase
                supabase_client.update(payload={
                                           "questions": questions_json
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
                                           "therapist_id": therapist_id,
                                           "questions": questions_json
                                       },
                                       table_name="patient_question_suggestions")
        except Exception as e:
            Logger().log_error(background_tasks=background_tasks,
                               description="Updating the question suggestions in a background task failed",
                               session_id=session_id,
                               therapist_id=therapist_id,
                               patient_id=patient_id)
            raise Exception(e)

    async def update_diarization_with_notification_data(self,
                                                        auth_manager: AuthManager,
                                                        supabase_client: SupabaseBaseClass,
                                                        openai_client: OpenAIBaseClass,
                                                        pinecone_client: PineconeBaseClass,
                                                        job_id: str,
                                                        session_id: str,
                                                        diarization_summary: str,
                                                        diarization: str) -> str:
        try:
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)

            session_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'diarization_job_id': job_id
                                                   },
                                                   table_name="session_reports")
            session_query_dict = session_query.dict()
            therapist_id = session_query_dict['data'][0]['therapist_id']
            patient_id = session_query_dict['data'][0]['patient_id']
            template = session_query_dict['data'][0]['diarization_template']
            session_date_raw = session_query_dict['data'][0]['session_date']
            session_date_formatted = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=session_date_raw,
                                                                                        incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)

            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         'id': therapist_id
                                                     },
                                                     table_name="therapists")
            assert (0 != len((therapist_query).data))
            language_code = therapist_query.dict()['data'][0]["language_preference"]
            mini_summary = await ChartWiseAssistant().create_session_mini_summary(session_notes=diarization_summary,
                                                                                  therapist_id=therapist_id,
                                                                                  language_code=language_code,
                                                                                  auth_manager=auth_manager,
                                                                                  openai_client=openai_client,
                                                                                  session_id=session_id)

            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'id': patient_id,
                                                       'therapist_id': therapist_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data))

            patient_query_dict = patient_query.dict()
            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                patient_last_session_date = session_date_formatted
            else:
                formatted_date = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=patient_last_session_date,
                                                                                    incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
                patient_last_session_date = datetime_handler.retrieve_most_recent_date(first_date=session_date_formatted,
                                                                                       first_date_format=datetime_handler.DATE_FORMAT,
                                                                                       second_date=formatted_date,
                                                                                       second_date_format=datetime_handler.DATE_FORMAT)

            supabase_client.update(table_name="patients",
                                   payload={
                                       "last_session_date": patient_last_session_date,
                                       "total_sessions": (1 + (patient_query_dict['data'][0]['total_sessions'])),
                                   },
                                   filters={
                                       'id': patient_id
                                   })

            if template == SessionNotesTemplate.SOAP.value:
                soap_notes = await self.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                    openai_client=openai_client,
                                                                    therapist_id=therapist_id,
                                                                    session_notes_text=diarization_summary,
                                                                    session_id=session_id)
                supabase_client.update(table_name="session_reports",
                                       payload={
                                           "notes_text": soap_notes,
                                           "notes_mini_summary": mini_summary,
                                           "diarization_summary": diarization_summary,
                                           "diarization": diarization,
                                           "last_updated": now_timestamp,
                                       },
                                       filters={
                                           'diarization_job_id': job_id
                                       })
            else:
                assert template == SessionNotesTemplate.FREE_FORM.value, f"Unexpected template: {template}"
                supabase_client.update(table_name="session_reports",
                                       payload={
                                           "notes_text": diarization_summary,
                                           "notes_mini_summary": mini_summary,
                                           "diarization_summary": diarization_summary,
                                           "diarization": diarization,
                                           "last_updated": now_timestamp,
                                       },
                                       filters={
                                           'diarization_job_id': job_id
                                       })

            await pinecone_client.insert_session_vectors(index_id=therapist_id,
                                                         namespace=patient_id,
                                                         text=diarization_summary,
                                                         therapy_session_date=session_date_formatted,
                                                         auth_manager=auth_manager,
                                                         openai_client=openai_client,
                                                         session_id=session_id)
        except Exception as e:
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

            patient_response_dict = patient_query.dict()
            patient_name = patient_response_dict['data'][0]['first_name']
            patient_gender = patient_response_dict['data'][0]['gender']
            last_session_date = patient_response_dict['data'][0]['last_session_date']
            session_number = 1 + patient_response_dict['data'][0]['total_sessions']

            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         "id": therapist_id
                                                     },
                                                     table_name="therapists")
            therapist_response_dict = therapist_query.dict()
            therapist_name = therapist_response_dict['data'][0]['first_name']
            language_code = therapist_response_dict['data'][0]['language_preference']
            therapist_gender = therapist_response_dict['data'][0]['gender']

            if len(last_session_date or '') > 0:
                session_date_override = PineconeQuerySessionDateOverride(output_prefix_override="*** The following data is from the patient's last session with the therapist ***\n",
                                                                         output_suffix_override="*** End of data associated with the patient's last session with the therapist ***",
                                                                         session_date=last_session_date)
            else:
                session_date_override = None

            briefing = await self.chartwise_assistant.create_briefing(index_id=therapist_id,
                                                                       namespace=patient_id,
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
                                                                       pinecone_client=pinecone_client,
                                                                       session_date_override=session_date_override)

            briefing_query = supabase_client.select(fields="*",
                                                    filters={
                                                        'therapist_id': therapist_id,
                                                        'patient_id': patient_id
                                                    },
                                                    table_name="patient_briefings")

            if 0 != len((briefing_query).data):
                # Update existing result in Supabase
                supabase_client.update(payload={
                                           "briefing": briefing
                                       },
                                       filters={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                       },
                                       table_name="patient_briefings")
            else:
                # Insert result to Supabase
                supabase_client.insert(payload={
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

    async def update_patient_frequent_topics(self,
                                             therapist_id: str,
                                             patient_id: str,
                                             auth_manager: AuthManager,
                                             environment: str,
                                             session_id: str,
                                             background_tasks: BackgroundTasks,
                                             openai_client: OpenAIBaseClass,
                                             pinecone_client: PineconeBaseClass,
                                             supabase_client: SupabaseBaseClass):
        try:
            therapist_query = supabase_client.select(fields="*",
                                                     filters={
                                                         'id': therapist_id
                                                     },
                                                     table_name="therapists")
            assert (0 != len((therapist_query).data)), "Did not find any store data for incoming user."

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            frequent_topics = await ChartWiseAssistant().fetch_frequent_topics(language_code=language_code,
                                                                               session_id=session_id,
                                                                               index_id=therapist_id,
                                                                               namespace=patient_id,
                                                                               environment=environment,
                                                                               pinecone_client=pinecone_client,
                                                                               openai_client=openai_client,
                                                                               auth_manager=auth_manager,
                                                                               patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                               patient_gender=patient_gender)
            assert 'topics' in frequent_topics, "Missing json key for frequent topics response. Please try again"

            topics_query = supabase_client.select(fields="*",
                                                  filters={
                                                      'therapist_id': therapist_id,
                                                      'patient_id': patient_id
                                                  },
                                                  table_name="patient_frequent_topics")

            if 0 != len((topics_query).data):
                # Update existing result in Supabase
                supabase_client.update(payload={
                                           "frequent_topics": frequent_topics
                                       },
                                       filters={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                       },
                                       table_name="patient_frequent_topics")
            else:
                # Insert result to Supabase
                supabase_client.insert(payload={
                                           "patient_id": patient_id,
                                           "therapist_id": therapist_id,
                                           "frequent_topics": frequent_topics
                                       },
                                       table_name="patient_frequent_topics")
        except Exception as e:
            Logger().log_error(background_tasks=background_tasks,
                               description="Updating the frequent topics in a background task failed",
                               session_id=session_id,
                               therapist_id=therapist_id,
                               patient_id=patient_id)
            raise Exception(e)

    async def generate_insights_after_session_data_updates(self,
                                                           background_tasks: BackgroundTasks,
                                                           therapist_id: str,
                                                           patient_id: str,
                                                           auth_manager: AuthManager,
                                                           environment: str,
                                                           session_id: str,
                                                           pinecone_client: PineconeBaseClass,
                                                           openai_client: OpenAIBaseClass,
                                                           supabase_client: SupabaseBaseClass):

        # Given our chat history may be stale based on the new data, let's clear anything we have
        background_tasks.add_task(openai_client.clear_chat_history)

        # Update this patient's frequent topics for future fetches.
        background_tasks.add_task(self.update_patient_frequent_topics,
                                  therapist_id,
                                  patient_id,
                                  auth_manager,
                                  environment,
                                  session_id,
                                  background_tasks,
                                  openai_client,
                                  pinecone_client,
                                  supabase_client)

        # Update this patient's question suggestions for future fetches.
        background_tasks.add_task(self.update_question_suggestions,
                                  therapist_id,
                                  patient_id,
                                  background_tasks,
                                  auth_manager,
                                  environment,
                                  session_id,
                                  openai_client,
                                  pinecone_client,
                                  supabase_client)

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
