from datetime import datetime

from pinecone import NotFoundException
from supabase import Client

from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import (AssistantQuery,
                               QuestionSuggestionsParams,
                               SessionHistorySummary,
                               SessionNotesInsert,
                               SessionNotesUpdate,
                               SummaryConfiguration,)
from ...internal.utilities import datetime_handler
from ...vectors import vector_writer
from ...vectors.vector_query import VectorQueryWorker

class AssistantManager(AssistantManagerBaseClass):

    def process_new_session_data(self,
                                 auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert,
                                 datastore_access_token: str,
                                 datastore_refresh_token: str):
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                            refresh_token=datastore_refresh_token)
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            datastore_client.table('session_reports').insert({
                "notes_text": body.text,
                "session_date": body.date,
                "patient_id": body.patient_id,
                "source": body.source.value,
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
                       body: SessionNotesUpdate,
                       datastore_access_token: str,
                       datastore_refresh_token: str):
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                            refresh_token=datastore_refresh_token)

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            update_result = datastore_client.table('session_reports').update({
                "notes_text": body.text,
                "last_updated": now_timestamp,
                "source": body.source.value,
                "session_date": body.date,
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
                       session_report_id: str,
                       datastore_access_token: str,
                       datastore_refresh_token: str):
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                            refresh_token=datastore_refresh_token)

            delete_result = datastore_client.table('session_reports').delete().eq('id', session_report_id).execute()
            delete_result_dict = delete_result.dict()
            assert len(delete_result_dict['data']) > 0, "No session found with the incoming session_report_id"

            therapist_id = delete_result_dict['data'][0]['therapist_id']
            patient_id = delete_result_dict['data'][0]['patient_id']
            session_date_raw = delete_result_dict['data'][0]['session_date']
            session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date_raw)

            # Delete vector embeddings
            vector_writer.delete_session_vectors(index_id=therapist_id,
                                                 namespace=patient_id,
                                                 date=session_date_formatted)
        except Exception as e:
            raise Exception(e)

    def delete_all_sessions_for_patient(self,
                                        therapist_id: str,
                                        patient_id: str):
        try:
            vector_writer.delete_session_vectors(index_id=therapist_id,
                                                 namespace=patient_id)
        except NotFoundException:
            # Index doesn't exist, failing silently. Patient is being deleted prior to having any
            # data in our vector db
            pass
        except Exception as e:
            raise Exception(e)

    def delete_all_sessions_for_therapist(self,
                                          id: str):
        try:
            vector_writer.delete_index(id)
        except Exception as e:
            raise Exception(e)

    def query_session(self,
                      auth_manager: AuthManagerBaseClass,
                      query: AssistantQuery,
                      session_id: str,
                      api_method: str,
                      endpoint_name: str,
                      environment: str,
                      datastore_access_token: str,
                      datastore_refresh_token: str):
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(datastore_access_token,
                                                                            datastore_refresh_token)

            # Confirm that the incoming patient id is assigned to the incoming therapist id.
            patient_query = datastore_client.from_('patients').select('*').eq('therapist_id', query.therapist_id).eq('id',
                                                                                                        query.patient_id).execute()
            patient_therapist_match = (0 != len((patient_query).data))
            assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            therapist_query = datastore_client.from_('therapists').select('*').eq('id', query.therapist_id).execute()
            assert (0 != len((therapist_query).data))

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            response = VectorQueryWorker().query_store(index_id=query.therapist_id,
                                                       namespace=query.patient_id,
                                                       patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                       patient_gender=patient_gender,
                                                       input=query.text,
                                                       response_language_code=language_code,
                                                       session_id=session_id,
                                                       endpoint_name=endpoint_name,
                                                       method=api_method,
                                                       environment=environment,
                                                       auth_manager=auth_manager)

            return {"response": response}
        except Exception as e:
            raise Exception(e)

    def fetch_todays_greeting(self,
                              client_tz_identifier: str,
                              therapist_id: str,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str,
                              environment: str,
                              auth_manager: AuthManagerBaseClass,
                              datastore_access_token: str,
                              datastore_refresh_token: str) -> str:
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                            refresh_token=datastore_refresh_token)
            therapist_query = datastore_client.from_('therapists').select('*').eq('id', therapist_id).execute()
            assert (0 != len((therapist_query).data)), "No user was found with the incoming id"

            therapist_query_dict = therapist_query.dict()
            addressing_name = therapist_query_dict['data'][0]["first_name"]
            language_code = therapist_query_dict['data'][0]["language_preference"]
            therapist_gender = therapist_query_dict['data'][0]["gender"]
            result = VectorQueryWorker().create_greeting(therapist_name=addressing_name,
                                                         therapist_gender=therapist_gender,
                                                         language_code=language_code,
                                                         tz_identifier=client_tz_identifier,
                                                         session_id=session_id,
                                                         endpoint_name=endpoint_name,
                                                         therapist_id=therapist_id,
                                                         method=api_method,
                                                         environment=environment,
                                                         auth_manager=auth_manager)
            return result
        except Exception as e:
            raise Exception(e)

    def fetch_question_suggestions(self,
                                   body: QuestionSuggestionsParams,
                                   auth_manager: AuthManagerBaseClass,
                                   environment: str,
                                   session_id: str,
                                   endpoint_name: str,
                                   api_method: str,
                                   datastore_access_token: str,
                                   datastore_refresh_token: str):
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                            refresh_token=datastore_refresh_token)

            therapist_query = datastore_client.from_('therapists').select('*').eq('id', body.therapist_id).execute()
            assert (0 != len((therapist_query).data)), "Did not find any store data for incoming user."

            language_code = therapist_query.dict()['data'][0]["language_preference"]

            patient_query = datastore_client.from_('patients').select('*').eq('therapist_id', body.therapist_id).eq('id',
                                                                                                                    body.patient_id).execute()
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            response = VectorQueryWorker().create_question_suggestions(language_code=language_code,
                                                                       session_id=session_id,
                                                                       endpoint_name=endpoint_name,
                                                                       index_id=body.therapist_id,
                                                                       namespace=body.patient_id,
                                                                       method=api_method,
                                                                       environment=environment,
                                                                       auth_manager=auth_manager,
                                                                       patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                       patient_gender=patient_gender)

            assert 'questions' in response, "Something went wrong in generating a response. Please try again"
            return response
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
                               configuration: SummaryConfiguration,
                               datastore_access_token: str,
                               datastore_refresh_token: str):
        try:
            datastore_client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                    refresh_token=datastore_refresh_token)
            patient_response = datastore_client.from_('patients').select('*').eq('therapist_id', body.therapist_id).eq('id',
                                                                                                                    body.patient_id).execute()
            assert (0 != len((patient_response).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_response_dict = patient_response.dict()
            patient_name = patient_response_dict['data'][0]['first_name']
            patient_gender = patient_response_dict['data'][0]['gender']

            therapist_response = datastore_client.table('therapists').select('*').eq("id", body.therapist_id).execute()
            therapist_response_dict = therapist_response.dict()
            therapist_name = therapist_response_dict['data'][0]['first_name']
            language_code = therapist_response_dict['data'][0]['language_preference']
            therapist_gender = therapist_response_dict['data'][0]['gender']

            number_session_response = datastore_client.table('session_reports').select('*').eq("patient_id", body.patient_id).execute()
            session_number = 1 + len(number_session_response.dict()['data'])

            result = VectorQueryWorker().create_summary(index_id=body.therapist_id,
                                                        namespace=body.patient_id,
                                                        environment=environment,
                                                        language_code=language_code,
                                                        session_id=session_id,
                                                        endpoint_name=endpoint_name,
                                                        method=api_method,
                                                        patient_name=patient_name,
                                                        patient_gender=patient_gender,
                                                        therapist_name=therapist_name,
                                                        therapist_gender=therapist_gender,
                                                        session_number=session_number,
                                                        auth_manager=auth_manager,
                                                        configuration=configuration)

            assert 'summary' in result, "Something went wrong in generating a response. Please try again"
            return result
        except Exception as e:
            raise Exception(e)
