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
    """
    def process_new_session_data(auth_manager: AuthManagerBaseClass,
                                 body: SessionNotesInsert):
        pass
    
    """
    Takes care of updating a session's data.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    body – the new data associated with the session.
    """
    def update_session(auth_manager: AuthManagerBaseClass,
                       body: SessionNotesUpdate):
        pass

    """
    Takes care of deleting a session's data.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    session_report_id – the id associated with the session to be deleted.
    """
    def delete_session(auth_manager: AuthManagerBaseClass,
                       session_report_id: str):
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
    auth_entity – the auth entity that enabled the incoming request.
    """
    def query_session(auth_manager: AuthManagerBaseClass,
                      query: AssistantQuery,
                      session_id: str,
                      api_method: str,
                      endpoint_name: str,
                      environment: str,
                      auth_entity: str):
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
    auth_entity – the auth entity that enabled the incoming request.
    """
    def fetch_todays_greeting(body: Greeting,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str,
                              environment: str,
                              auth_manager: AuthManagerBaseClass,
                              auth_entity: str):
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
    auth_entity – the auth entity that enabled the incoming request.
    configuration – the configuration for creating the summary.]
    """
    def create_patient_summary(body: SessionHistorySummary,
                               auth_manager: AuthManagerBaseClass,
                               environment: str,
                               session_id: str,
                               endpoint_name: str,
                               api_method: str,
                               auth_entity: str,
                               configuration: SummaryConfiguration):
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
    auth_entity – the auth entity that enabled the incoming request.
    """
    def fetch_question_suggestions(body: QuestionSuggestionsParams,
                                   auth_manager: AuthManagerBaseClass,
                                   environment: str,
                                   session_id: str,
                                   endpoint_name: str,
                                   api_method: str,
                                   auth_entity: str):
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
