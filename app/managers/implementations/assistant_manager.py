from datetime import datetime

from supabase import Client

from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import (AssistantQuery,
                               SessionNotesInsert,
                               SessionNotesTemplate,
                               SessionNotesUpdate,
                               BriefingConfiguration,)
from ...internal.utilities import datetime_handler
from ...vectors import vector_writer
from ...vectors.vector_query import VectorQueryWorker

class AssistantManager(AssistantManagerBaseClass):

    def process_new_session_data(self,
                                 auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert,
                                 datastore_access_token: str,
                                 datastore_refresh_token: str,
                                 session_id: str,
                                 endpoint_name: str,
                                 method: str,
                                 environment: str,) -> str:
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                            refresh_token=datastore_refresh_token)
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            insert_result = datastore_client.table('session_reports').insert({
                "notes_text": body.text,
                "session_date": body.date,
                "patient_id": body.patient_id,
                "source": body.source.value,
                "last_updated": now_timestamp,
                "therapist_id": body.therapist_id}).execute()
            session_notes_id = insert_result.dict()['data'][0]['id']

            query_result = datastore_client.from_('patients').select('*').eq('id', body.patient_id).execute()
            query_result_dict = query_result.dict()
            patient_full_name = " ".join([query_result_dict['data'][0]['first_name'],
                                          query_result_dict['data'][0]['last_name']])

            # Upload vector embeddings
            vector_writer.insert_session_vectors(index_id=body.therapist_id,
                                                 namespace=body.patient_id,
                                                 text=body.text,
                                                 date=body.date,
                                                 patient_name=patient_full_name,
                                                 endpoint_name=endpoint_name,
                                                 method=method,
                                                 auth_manager=auth_manager,
                                                 environment=environment,
                                                 session_id=session_id)

            return session_notes_id
        except Exception as e:
            raise Exception(e)

    def update_session(self,
                       auth_manager: AuthManagerBaseClass,
                       body: SessionNotesUpdate,
                       datastore_access_token: str,
                       datastore_refresh_token: str,
                       environment: str,
                       endpoint_name: str,
                       method: str):
        try:
            datastore_client: Client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                            refresh_token=datastore_refresh_token)

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            update_result = datastore_client.table('session_reports').update({
                "notes_text": body.text,
                "last_updated": now_timestamp,
                "source": body.source.value,
                "session_date": body.date,
                "diarization": body.diarization,
            }).eq('id', body.session_notes_id).execute()

            update_result_dict = update_result.dict()
            session_date_raw = update_result_dict['data'][0]['session_date']
            session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date_raw)
            patient_id = update_result_dict['data'][0]['patient_id']

            patient_query = datastore_client.from_('patients').select('*').eq('id', patient_id).execute().dict()
            patient_full_name = " ".join([patient_query['data'][0]['first_name'],
                                          patient_query['data'][0]['last_name']])

            # Upload vector embeddings
            vector_writer.update_session_vectors(index_id=body.therapist_id,
                                                namespace=body.patient_id,
                                                text=body.text,
                                                date=session_date_formatted,
                                                environment=environment,
                                                endpoint_name=endpoint_name,
                                                method=method,
                                                patient_name=patient_full_name,
                                                auth_manager=auth_manager,)
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

    def adapt_session_notes_to_soap(self,
                                    auth_manager: AuthManagerBaseClass,
                                    therapist_id: str,
                                    session_notes_text: str) -> str:
        try:
            soap_report = VectorQueryWorker().create_soap_report(text=session_notes_text,
                                                                 therapist_id=therapist_id,
                                                                 auth_manager=auth_manager)
            return soap_report
        except Exception as e:
            raise Exception(e)

    def delete_all_sessions_for_patient(self,
                                        therapist_id: str,
                                        patient_id: str):
        try:
            vector_writer.delete_session_vectors(index_id=therapist_id,
                                                 namespace=patient_id)
        except Exception as e:
            # Index doesn't exist, failing silently. Patient is being deleted prior to having any
            # data in our vector db
            pass

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
                                   therapist_id: str,
                                   patient_id: str,
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

            therapist_query = datastore_client.from_('therapists').select('*').eq('id', therapist_id).execute()
            assert (0 != len((therapist_query).data)), "Did not find any store data for incoming user."

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            patient_query = datastore_client.from_('patients').select('*').eq('therapist_id', therapist_id).eq('id',
                                                                                                               patient_id).execute()
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            response = VectorQueryWorker().create_question_suggestions(language_code=language_code,
                                                                       session_id=session_id,
                                                                       endpoint_name=endpoint_name,
                                                                       index_id=therapist_id,
                                                                       namespace=patient_id,
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
                                                  diarization: str,
                                                  endpoint_name: str,
                                                  method: str,):
        try:
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            datastore_client = auth_manager.datastore_admin_instance()

            session_query = datastore_client.from_('session_reports').select('*').eq('diarization_job_id', job_id).execute()
            session_query_dict = session_query.dict()
            therapist_id = session_query_dict['data'][0]['therapist_id']
            patient_id = session_query_dict['data'][0]['patient_id']
            template = session_query_dict['data'][0]['diarization_template']
            session_date_raw = session_query_dict['data'][0]['session_date']
            session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date_raw)

            if template == SessionNotesTemplate.SOAP.value:
                soap_summary = self.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                therapist_id=therapist_id,
                                                                session_notes_text=summary)
                datastore_client.table('session_reports').update({
                    "notes_text": soap_summary,
                    "diarization": diarization,
                    "last_updated": now_timestamp,
                    "diarization_job_id": None,
                }).eq('diarization_job_id', job_id).execute()
            else:
                assert template == SessionNotesTemplate.FREE_FORM.value, f"Unexpected template: {template}"
                datastore_client.table('session_reports').update({
                    "notes_text": summary,
                    "diarization": diarization,
                    "last_updated": now_timestamp,
                    "diarization_job_id": None,
                }).eq('diarization_job_id', job_id).execute()

            query_result = datastore_client.from_('patients').select('*').eq('id', patient_id).execute()
            query_result_dict = query_result.dict()
            patient_full_name = " ".join([query_result_dict['data'][0]['first_name'],
                                        query_result_dict['data'][0]['last_name']])

            # Upload vector embeddings
            vector_writer.insert_session_vectors(index_id=therapist_id,
                                                 namespace=patient_id,
                                                 text=summary,
                                                 patient_name=patient_full_name,
                                                 date=session_date_formatted,
                                                 auth_manager=auth_manager,
                                                 endpoint_name=endpoint_name,
                                                 method=method)
        except Exception as e:
            raise Exception(e)

    async def create_patient_summary(self,
                                     therapist_id: str,
                                     patient_id: str,
                                     auth_manager: AuthManagerBaseClass,
                                     environment: str,
                                     session_id: str,
                                     endpoint_name: str,
                                     api_method: str,
                                     configuration: BriefingConfiguration,
                                     datastore_access_token: str,
                                     datastore_refresh_token: str):
        try:
            datastore_client = auth_manager.datastore_user_instance(access_token=datastore_access_token,
                                                                    refresh_token=datastore_refresh_token)
            patient_response = datastore_client.from_('patients').select('*').eq('therapist_id', therapist_id).eq('id',
                                                                                                                  patient_id).execute()
            assert (0 != len((patient_response).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_response_dict = patient_response.dict()
            patient_name = patient_response_dict['data'][0]['first_name']
            patient_gender = patient_response_dict['data'][0]['gender']

            therapist_response = datastore_client.table('therapists').select('*').eq("id", therapist_id).execute()
            therapist_response_dict = therapist_response.dict()
            therapist_name = therapist_response_dict['data'][0]['first_name']
            language_code = therapist_response_dict['data'][0]['language_preference']
            therapist_gender = therapist_response_dict['data'][0]['gender']

            number_session_response = datastore_client.table('session_reports').select('*').eq("patient_id", patient_id).execute()
            session_number = 1 + len(number_session_response.dict()['data'])

            result = await VectorQueryWorker().create_briefing(index_id=therapist_id,
                                                               namespace=patient_id,
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

    def fetch_frequent_topics(self,
                              therapist_id: str,
                              patient_id: str,
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

            therapist_query = datastore_client.from_('therapists').select('*').eq('id', therapist_id).execute()
            assert (0 != len((therapist_query).data)), "Did not find any store data for incoming user."

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            patient_query = datastore_client.from_('patients').select('*').eq('therapist_id', therapist_id).eq('id',
                                                                                                               patient_id).execute()
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            response = VectorQueryWorker().fetch_frequent_topics(language_code=language_code,
                                                                 session_id=session_id,
                                                                 endpoint_name=endpoint_name,
                                                                 index_id=therapist_id,
                                                                 namespace=patient_id,
                                                                 method=api_method,
                                                                 environment=environment,
                                                                 auth_manager=auth_manager,
                                                                 patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                 patient_gender=patient_gender)

            error_message = "Something went wrong in generating a response. Please try again"
            assert 'topics' in response, error_message
            assert 'topic' in response['topics'][0], error_message
            assert 'percentage' in response['topics'][0], error_message
            return response
        except Exception as e:
            raise Exception(e)
