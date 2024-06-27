from abc import ABC

from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.model import (AssistantQuery,
                              Greeting,
                              SessionHistorySummary,
                              SessionNotesDelete,
                              SessionNotesInsert,
                              SessionNotesUpdate)

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
    body – the data associated with the session to be deleted.
    """
    def delete_session(auth_manager: AuthManagerBaseClass,
                       body: SessionNotesDelete):
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
    """
    def query_session(self,
                      auth_manager: AuthManagerBaseClass,
                      query: AssistantQuery,
                      session_id: str,
                      api_method: str,
                      endpoint_name: str,
                      environment: str):
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
    """
    def fetch_todays_greeting(self,
                              body: Greeting,
                              session_id: str,
                              endpoint_name: str,
                              api_method: str,
                              environment: str,
                              auth_manager: AuthManagerBaseClass):
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
    """
    def create_patient_summary(self,
                               body: SessionHistorySummary,
                               auth_manager: AuthManagerBaseClass,
                               environment: str,
                               session_id: str,
                               endpoint_name: str,
                               api_method: str):
        pass
