from datetime import datetime

from fastapi import status

from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import (AssistantQuery,
                               Greeting,
                               SessionNotesDelete,
                               SessionNotesInsert,
                               SessionNotesUpdate)
from ...internal.utilities import datetime_handler
from ...vectors import vector_query, vector_writer

class AssistantManager(AssistantManagerBaseClass):

    def process_new_session_data(self,
                                 auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert):
        try:
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
                      endpoint_name: str):
        try:
            datastore_client = auth_manager.datastore_user_instance(query.datastore_access_token,
                                                                    query.datastore_refresh_token)

            # Confirm that the incoming patient id is assigned to the incoming therapist id.
            patient_therapist_match = (0 != len(
                (datastore_client.from_('patients').select('*').eq('therapist_id', query.therapist_id).eq('id',
                                                                                                        query.patient_id).execute()
            ).data))

            assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."
            
            # Go through with the query
            response: vector_query.QueryResult = vector_query.query_store(index_id=query.therapist_id,
                                                                        namespace=query.patient_id,
                                                                        input=query.text,
                                                                        response_language_code=query.response_language_code,
                                                                        session_id=session_id,
                                                                        endpoint_name=endpoint_name,
                                                                        method=api_method)

            assert response.status_code == status.HTTP_200_OK, "Something went wrong when executing the query"

            return {"response": response.response_token}
        except Exception as e:
            raise Exception(e)

    def fetch_todays_greeting(self,
                              body: Greeting,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str):
        try:
            result = vector_query.create_greeting(name=body.addressing_name,
                                                language_code=body.response_language_code,
                                                tz_identifier=body.client_tz_identifier,
                                                session_id=session_id,
                                                endpoint_name=endpoint_name,
                                                therapist_id=body.therapist_id,
                                                method=api_method)
            assert result.status_code == status.HTTP_200_OK
            return result
        except Exception as e:
            raise Exception(e)
