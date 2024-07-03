from datetime import datetime

from fastapi import status

from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import (AssistantQuery,
                               Greeting,
                               SessionHistorySummary,
                               SessionNotesDelete,
                               SessionNotesInsert,
                               SessionNotesUpdate)
from ...internal.utilities import datetime_handler
from ...vectors import vector_writer
from ...vectors.vector_query import VectorQueryWorker

class AssistantManager(AssistantManagerBaseClass):

    def process_new_session_data(self,
                                 auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert):
        try:
            assert datetime_handler.is_valid_date(body.date), "Received invalid date"

            datastore_client = auth_manager.datastore_user_instance(body.datastore_access_token,
                                                                    body.datastore_refresh_token)
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            datastore_client.table('session_reports').insert({
                "notes_text": body.text,
                "session_date": body.date,
                "patient_id": body.patient_id,
                "source": body.source,
                "last_updated": now_timestamp,
                "therapist_id": body.therapist_id}).execute()

            # Upload vector embeddings
            vector_writer.insert_session_vectors(index_id=body.therapist_id,
                                                    namespace=body.patient_id,
                                                    text=body.text,
                                                    date=body.date)
        except Exception as e:
            raise Exception(e)

    def update_session(self,
                       auth_manager: AuthManagerBaseClass,
                       body: SessionNotesUpdate):
        try:
            datastore_client = auth_manager.datastore_user_instance(body.datastore_access_token,
                                                                    body.datastore_refresh_token)

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            update_result = datastore_client.table('session_reports').update({
                "notes_text": body.text,
                "last_updated": now_timestamp,
                "session_diarization": body.diarization,
            }).eq('id', body.session_notes_id).execute()

            session_date_raw = update_result.dict()['data'][0]['session_date']
            session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date_raw)

            # Upload vector embeddings
            vector_writer.update_session_vectors(index_id=body.therapist_id,
                                                namespace=body.patient_id,
                                                text=body.text,
                                                date=session_date_formatted)
        except Exception as e:
            raise Exception(e)

    def delete_session(self,
                       auth_manager: AuthManagerBaseClass,
                       body: SessionNotesDelete):
        try:
            datastore_client = auth_manager.datastore_user_instance(body.datastore_access_token,
                                                                    body.datastore_refresh_token)

            delete_result = datastore_client.table('session_reports').delete().eq('id', body.session_notes_id).execute()

            session_date_raw = delete_result.dict()['data'][0]['session_date']
            session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date_raw)

            # Delete vector embeddings
            vector_writer.delete_session_vectors(index_id=body.therapist_id,
                                                namespace=body.patient_id,
                                                date=session_date_formatted)
        except Exception as e:
            raise Exception(e)

    def query_session(self,
                      auth_manager: AuthManagerBaseClass,
                      query: AssistantQuery,
                      session_id: str,
                      api_method: str,
                      endpoint_name: str,
                      environment: str,
                      auth_entity: str):
        try:
            datastore_client = auth_manager.datastore_user_instance(query.datastore_access_token,
                                                                    query.datastore_refresh_token)

            # Confirm that the incoming patient id is assigned to the incoming therapist id.
            patient_query = datastore_client.from_('patients').select('*').eq('therapist_id', query.therapist_id).eq('id',
                                                                                                        query.patient_id).execute()
            patient_therapist_match = (0 != len((patient_query).data))

            assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']

            # Go through with the query
            response = VectorQueryWorker().query_store(index_id=query.therapist_id,
                                                       namespace=query.patient_id,
                                                       patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                       input=query.text,
                                                       response_language_code=query.response_language_code,
                                                       session_id=session_id,
                                                       endpoint_name=endpoint_name,
                                                       method=api_method,
                                                       environment=environment,
                                                       auth_manager=auth_manager,
                                                       auth_entity=auth_entity)

            return {"response": response}
        except Exception as e:
            raise Exception(e)

    def fetch_todays_greeting(self,
                              body: Greeting,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str,
                              environment: str,
                              auth_manager: AuthManagerBaseClass,
                              auth_entity: str) -> str:
        try:
            result = VectorQueryWorker().create_greeting(name=body.addressing_name,
                                                         language_code=body.response_language_code,
                                                         tz_identifier=body.client_tz_identifier,
                                                         session_id=session_id,
                                                         endpoint_name=endpoint_name,
                                                         therapist_id=body.therapist_id,
                                                         method=api_method,
                                                         environment=environment,
                                                         auth_manager=auth_manager,
                                                         auth_entity=auth_entity)
            return result
        except Exception as e:
            raise Exception(e)

    def update_diarization_with_notification_data(self,
                                                  auth_manager: AuthManagerBaseClass,
                                                  job_id: str,
                                                  summary: str,
                                                  diarization: str):
        now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
        datastore_client = auth_manager.datastore_admin_instance()
        response = datastore_client.table('session_reports').update({
            "notes_text": summary,
            "session_diarization": diarization,
            "last_updated": now_timestamp,
        }).eq('session_diarization_job_id', job_id).execute()

        session_date_raw = response.dict()['data'][0]['session_date']
        session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date_raw)
        therapist_id = response.dict()['data'][0]['therapist_id']
        patient_id = response.dict()['data'][0]['patient_id']

        # Upload vector embeddings
        vector_writer.insert_session_vectors(index_id=therapist_id,
                                             namespace=patient_id,
                                             text=summary,
                                             date=session_date_formatted)

    def create_patient_summary(self,
                               body: SessionHistorySummary,
                               auth_manager: AuthManagerBaseClass,
                               environment: str,
                               session_id: str,
                               endpoint_name: str,
                               api_method: str,
                               auth_entity: str):
        try:
            datastore_client = auth_manager.datastore_user_instance(body.datastore_access_token,
                                                                    body.datastore_refresh_token)
            patient_response = datastore_client.table('patients').select('first_name').eq("id", body.patient_id).execute()
            patient_name = patient_response.dict()['data'][0]['first_name']

            therapist_response = datastore_client.table('therapists').select('first_name').eq("id", body.therapist_id).execute()
            therapist_name = therapist_response.dict()['data'][0]['first_name']

            number_session_response = datastore_client.table('session_reports').select('*').eq("patient_id", body.patient_id).execute()
            session_number = len(number_session_response.dict()['data'])

            result = VectorQueryWorker().create_summary(therapist_id=body.therapist_id,
                                                        patient_id=body.patient_id,
                                                        environment=environment,
                                                        session_id=session_id,
                                                        endpoint_name=endpoint_name,
                                                        api_method=api_method,
                                                        language_code=body.response_language_code,
                                                        therapist_name=therapist_name,
                                                        patient_name=patient_name,
                                                        session_number=session_number,
                                                        auth_manager=auth_manager,
                                                        auth_entity=auth_entity)
            return result
        except Exception as e:
            raise Exception(e)
