from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.model import (AssistantQuery,
                               Greeting,
                               SessionHistorySummary,
                               SessionNotesDelete,
                               SessionNotesInsert,
                               SessionNotesUpdate)

class FakeAssistantManager(AssistantManagerBaseClass):

    def process_new_session_data(auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert):
        ...

    def update_session(auth_manager: AuthManagerBaseClass,
                       body: SessionNotesUpdate):
        ...

    def delete_session(auth_manager: AuthManagerBaseClass,
                       body: SessionNotesDelete):
        ...

    def query_session(self,
                      auth_manager: AuthManagerBaseClass,
                      query: AssistantQuery,
                      session_id: str,
                      api_method: str,
                      endpoint_name: str,
                      environment: str,
                      auth_entity: str):
        ...

    def fetch_todays_greeting(self,
                              body: Greeting,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str,
                              environment: str,
                              auth_manager: AuthManagerBaseClass,
                              auth_entity: str):
        ...

    def create_patient_summary(self,
                               body: SessionHistorySummary,
                               auth_manager: AuthManagerBaseClass,
                               environment: str,
                               session_id: str,
                               endpoint_name: str,
                               api_method: str,
                               auth_entity: str):
        ...

    def update_diarization_with_notification_data(auth_manager: AuthManagerBaseClass,
                                                  job_id: str,
                                                  summary: str,
                                                  diarization: str):
        ...
