from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import (AssistantQuery,
                               PatientInsertPayload,
                               PatientUpdatePayload,
                               SessionNotesInsert,
                               SessionNotesUpdate)

class FakeAssistantManager(AssistantManagerBaseClass):

    FAKE_SESSION_NOTES_ID = "8fc1b533-304e-4a33-98ba-541fdd956c1f"
    fake_processed_diarization_result: str = None
    fake_insert_text: str = None

    async def process_new_session_data(self,
                                       auth_manager: AuthManagerBaseClass,
                                       body: SessionNotesInsert,
                                       datastore_access_token: str,
                                       datastore_refresh_token: str,
                                       session_id: str) -> str:
        self.fake_insert_text = body.text
        return self.FAKE_SESSION_NOTES_ID

    async def update_session(self,
                             auth_manager: AuthManagerBaseClass,
                             body: SessionNotesUpdate,
                             datastore_access_token: str,
                             datastore_refresh_token: str,
                             session_id: str):
        ...

    def delete_session(self,
                       auth_manager: AuthManagerBaseClass,
                       therapist_id: str,
                       session_report_id: str,
                       datastore_access_token: str,
                       datastore_refresh_token: str):
        ...

    async def add_patient(self,
                          auth_manager: AuthManagerBaseClass,
                          payload: PatientInsertPayload,
                          datastore_access_token: str,
                          datastore_refresh_token: str,
                          session_id: str) -> str:
        pass

    async def update_patient(self,
                             auth_manager: AuthManagerBaseClass,
                             payload: PatientUpdatePayload,
                             datastore_access_token: str,
                             datastore_refresh_token: str,
                             session_id: str):
        pass

    async def adapt_session_notes_to_soap(self,
                                          auth_manager: AuthManagerBaseClass,
                                          therapist_id: str,
                                          session_notes_text: str,
                                          session_id: str) -> str:
        return ""

    def delete_all_data_for_patient(self,
                                        therapist_id: str,
                                        patient_id: str):
        ...

    def delete_all_sessions_for_therapist(self, id: str):
        ...

    async def query_session(self,
                            auth_manager: AuthManagerBaseClass,
                            query: AssistantQuery,
                            session_id: str,
                            api_method: str,
                            endpoint_name: str,
                            environment: str,
                            datastore_access_token: str,
                            datastore_refresh_token: str):
        ...

    async def fetch_todays_greeting(self,
                                    client_tz_identifier: str,
                                    therapist_id: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    api_method: str,
                                    environment: str,
                                    auth_manager: AuthManagerBaseClass,
                                    datastore_access_token: str,
                                    datastore_refresh_token: str):
        ...

    async def create_patient_summary(self,
                                     therapist_id: str,
                                     patient_id: str,
                                     auth_manager: AuthManagerBaseClass,
                                     environment: str,
                                     session_id: str,
                                     endpoint_name: str,
                                     api_method: str,
                                     datastore_access_token: str,
                                     datastore_refresh_token: str):
        ...

    async def fetch_question_suggestions(self,
                                         therapist_id: str,
                                         patient_id: str,
                                         auth_manager: AuthManagerBaseClass,
                                         environment: str,
                                         session_id: str,
                                         endpoint_name: str,
                                         api_method: str,
                                         datastore_access_token: str,
                                         datastore_refresh_token: str):
        ...

    def update_diarization_with_notification_data(self,
                                                  auth_manager: AuthManagerBaseClass,
                                                  job_id: str,
                                                  summary: str,
                                                  diarization: str) -> str:
        self.fake_processed_diarization_result = diarization
        return ""

    async def fetch_frequent_topics(self,
                                    therapist_id: str,
                                    patient_id: str,
                                    auth_manager: AuthManagerBaseClass,
                                    environment: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    api_method: str,
                                    datastore_access_token: str,
                                    datastore_refresh_token: str):
        pass

    def fetch_preexisting_history(self,
                                  therapist_id: str,
                                  patient_id: str,
                                  auth_manager: AuthManagerBaseClass,
                                  datastore_access_token: str,
                                  datastore_refresh_token: str):
        pass
