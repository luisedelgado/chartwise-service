from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import (AssistantQuery,
                               Greeting,
                               QuestionSuggestionsParams,
                               SessionHistorySummary,
                               SessionNotesInsert,
                               SessionNotesUpdate,
                               SummaryConfiguration,)

class FakeAssistantManager(AssistantManagerBaseClass):

    FAKE_SESSION_NOTES_ID = "8fc1b533-304e-4a33-98ba-541fdd956c1f"
    fake_processed_diarization_result: str = None
    fake_insert_text: str = None

    def process_new_session_data(self,
                                 auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert,
                                 datastore_access_token: str,
                                 datastore_refresh_token: str):
        self.fake_insert_text = body.text

    def update_session(self,
                       auth_manager: AuthManagerBaseClass,
                       body: SessionNotesUpdate,
                       datastore_access_token: str,
                       datastore_refresh_token: str):
        ...

    def delete_session(self,
                       auth_manager: AuthManagerBaseClass,
                       session_report_id: str,
                       datastore_access_token: str,
                       datastore_refresh_token: str):
        ...

    def delete_all_sessions_for_patient(self,
                                        therapist_id: str,
                                        patient_id: str):
        ...

    def delete_all_sessions_for_therapist(self,
                                          id: str):
        ...

    def query_session(self,
                      auth_manager: AuthManagerBaseClass,
                      query: AssistantQuery,
                      session_id: str,
                      api_method: str,
                      endpoint_name: str,
                      environment: str,
                      datastore_access_token: str,
                      datastore_refresh_token: str):
        ...

    def fetch_todays_greeting(self,
                              body: Greeting,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str,
                              environment: str,
                              auth_manager: AuthManagerBaseClass,
                              datastore_access_token: str,
                              datastore_refresh_token: str):
        ...

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
        ...

    def fetch_question_suggestions(self,
                                   body: QuestionSuggestionsParams,
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
                                                  diarization: str):
        self.fake_processed_diarization_result = diarization
