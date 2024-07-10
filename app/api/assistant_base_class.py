from abc import ABC

from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.model import (AssistantQuery,
                              Greeting,
                              QuestionSuggestionsParams,
                              PatientDeletePayload,
                              SessionHistorySummary,
                              SessionNotesInsert,
                              SessionNotesUpdate,
                              SummaryConfiguration,
                              TherapistDeletePayload,)

class AssistantManagerBaseClass(ABC):

    """
    Takes care of processing a new session's data.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    body – the data associated with the session.
    datastore_access_token – the datastore access token to be used.
    datastore_refresh_token – the datastore refresh token to be used.
    """
    def process_new_session_data(auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert,
                                 datastore_access_token: str,
                                 datastore_refresh_token: str):
        pass
    
    """
    Takes care of updating a session's data.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    body – the new data associated with the session.
    datastore_access_token – the datastore access token to be used.
    datastore_refresh_token – the datastore refresh token to be used.
    """
    def update_session(auth_manager: AuthManagerBaseClass,
                       body: SessionNotesUpdate,
                       datastore_access_token: str,
                       datastore_refresh_token: str):
        pass

    """
    Takes care of deleting a session's data.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    session_report_id – the id associated with the session to be deleted.
    datastore_access_token – the datastore access token to be used.
    datastore_refresh_token – the datastore refresh token to be used.
    """
    def delete_session(auth_manager: AuthManagerBaseClass,
                       session_report_id: str,
                       datastore_access_token: str,
                       datastore_refresh_token: str):
        pass

    """
    Takes care of deleting all sessions associated with the incoming patient id.

    Arguments:
    body – the data associated with the sessions to be deleted.
    """
    def delete_all_sessions_for_patient(body: PatientDeletePayload):
        pass

    """
    Takes care of deleting all sessions associated with the incoming patient id.

    Arguments:
    body – the data associated with the sessions to be deleted.
    """
    def delete_all_sessions_for_therapist(self,
                                          body: TherapistDeletePayload):
        pass

    """
    Queries information about a given session.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    query – the data associated with the query.
    session_id – the current session id.
    api_method – the api method that triggered this query.
    endpoint_name – the endpoint name that triggered this query.
    environment – the current running environment.
    datastore_access_token – the datastore access token to be used.
    datastore_refresh_token – the datastore refresh token to be used.
    """
    def query_session(auth_manager: AuthManagerBaseClass,
                      query: AssistantQuery,
                      session_id: str,
                      api_method: str,
                      endpoint_name: str,
                      environment: str,
                      datastore_access_token: str,
                      datastore_refresh_token: str):
        pass

    """
    Creates a greeting for the current user and date.

    Arguments:
    body – the data associated with the greeting.
    session_id – the current session id.
    endpoint_name – the endpoint name that triggered this query.
    api_method – the api method that triggered this query.
    environment – the current running environment.
    auth_manager – the auth_manager to be leveraged.
    datastore_access_token – the datastore access token to be used.
    datastore_refresh_token – the datastore refresh token to be used.
    """
    def fetch_todays_greeting(body: Greeting,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str,
                              environment: str,
                              auth_manager: AuthManagerBaseClass,
                              datastore_access_token: str,
                              datastore_refresh_token: str):
        pass

    """
    Creates a summary about the given patient's session history.

    Arguments:
    body – the data associated with the summary.
    auth_manager – the auth_manager to be leveraged.
    environment – the current running environment.
    session_id – the current session id.
    endpoint_name – the endpoint name that triggered this query.
    api_method – the api method that triggered this query.
    configuration – the configuration for creating the summary.
    datastore_access_token – the datastore access token to be used.
    datastore_refresh_token – the datastore refresh token to be used.
    """
    def create_patient_summary(body: SessionHistorySummary,
                               auth_manager: AuthManagerBaseClass,
                               environment: str,
                               session_id: str,
                               endpoint_name: str,
                               api_method: str,
                               configuration: SummaryConfiguration,
                               datastore_access_token: str,
                               datastore_refresh_token: str):
        pass

    """
    Retrieves a set of questions to be presented as suggestions for the user on what to ask the assistant.

    Arguments:
    body – the payload associated with the question suggestions to be retrieved.
    auth_manager – the auth_manager to be leveraged.
    environment – the current running environment.
    session_id – the current session id.
    endpoint_name – the endpoint name that triggered this query.
    api_method – the api method that triggered this query.
    datastore_access_token – the datastore access token to be used.
    datastore_refresh_token – the datastore refresh token to be used.
    """
    def fetch_question_suggestions(body: QuestionSuggestionsParams,
                                   auth_manager: AuthManagerBaseClass,
                                   environment: str,
                                   session_id: str,
                                   endpoint_name: str,
                                   api_method: str,
                                   datastore_access_token: str,
                                   datastore_refresh_token: str):
        pass

    """
    Updates a diarization entry with data coming from Speechmatics' notification service.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    job_id – the id of the job that ran.
    summary – the session summary.
    diarization – the diarized session.
    """
    def update_diarization_with_notification_data(auth_manager: AuthManagerBaseClass,
                                                  job_id: str,
                                                  summary: str,
                                                  diarization: str):
        pass
