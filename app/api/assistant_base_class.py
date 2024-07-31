from abc import ABC

from ..api.supabase_base_class import SupabaseBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.model import (AssistantQuery,
                              PatientInsertPayload,
                              PatientUpdatePayload,
                              SessionNotesInsert,
                              SessionNotesUpdate)

class AssistantManagerBaseClass(ABC):

    """
    Takes care of processing a new session's data.
    Returns the session notes' id.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    body – the data associated with the session.
    session_id – the session id.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def process_new_session_data(auth_manager: AuthManagerBaseClass,
                                       body: SessionNotesInsert,
                                       session_id: str,
                                       supabase_manager: SupabaseBaseClass) -> str:
        pass

    """
    Takes care of updating a session's data.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    body – the new data associated with the session.
    session_id – the session id.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def update_session(auth_manager: AuthManagerBaseClass,
                             body: SessionNotesUpdate,
                             session_id: str,
                             supabase_manager: SupabaseBaseClass):
        pass

    """
    Takes care of deleting a session's data.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    therapist_id – the therapist_id associated with the session report.
    session_report_id – the id associated with the session to be deleted.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    def delete_session(auth_manager: AuthManagerBaseClass,
                       therapist_id: str,
                       session_report_id: str,
                       supabase_manager: SupabaseBaseClass):
        pass

    """
    Adds a new patient and returns the patient id.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    payload – the payload containing the data with which to create the patient.
    session_id – the session id.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def add_patient(auth_manager: AuthManagerBaseClass,
                          payload: PatientInsertPayload,
                          session_id: str,
                          supabase_manager: SupabaseBaseClass) -> str:
        pass

    """
    Updates a patient.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    payload – the payload containing the data with which to update the patient.
    session_id – the session id.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def update_patient(auth_manager: AuthManagerBaseClass,
                             payload: PatientUpdatePayload,
                             session_id: str,
                             supabase_manager: SupabaseBaseClass):
        pass

    """
    Adapts the incoming session notes to the SOAP format, and returns the result.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    therapist_id – the id associated with the therapist user.
    session_notes_text – the session notes to be adapted into SOAP.
    session_id – the session id
    """
    async def adapt_session_notes_to_soap(auth_manager: AuthManagerBaseClass,
                                          therapist_id: str,
                                          session_notes_text: str,
                                          session_id: str) -> str:
        pass

    """
    Takes care of deleting all sessions associated with the incoming patient id.

    Arguments:
    therapist_id – the therapist associated with the patient sessions to be deleted.
    patient_id – the patient_id associated with the sessions to be deleted.
    """
    def delete_all_data_for_patient(therapist_id: str, patient_id: str):
        pass

    """
    Takes care of deleting all sessions associated with the incoming patient id.

    Arguments:
    id – the id associated with the therapist whose sessions are to be deleted.
    """
    def delete_all_sessions_for_therapist(id: str):
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
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def query_session(auth_manager: AuthManagerBaseClass,
                            query: AssistantQuery,
                            session_id: str,
                            api_method: str,
                            endpoint_name: str,
                            environment: str,
                            supabase_manager: SupabaseBaseClass):
        pass

    """
    Creates a greeting for the current user and date.

    Arguments:
    client_tz_identifier – the timezone associated with the client.
    therapist_id – the therapist_id associated with the user.
    session_id – the current session id.
    endpoint_name – the endpoint name that triggered this query.
    api_method – the api method that triggered this query.
    environment – the current running environment.
    auth_manager – the auth_manager to be leveraged.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def fetch_todays_greeting(client_tz_identifier: str,
                                    therapist_id: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    api_method: str,
                                    environment: str,
                                    auth_manager: AuthManagerBaseClass,
                                    supabase_manager: SupabaseBaseClass):
        pass

    """
    Creates a summary about the given patient's session history.

    Arguments:
    therapist_id – the id associated with the user.
    patient_id – the id associated with the patient whose presession tray will be fetched.
    auth_manager – the auth_manager to be leveraged.
    environment – the current running environment.
    session_id – the current session id.
    endpoint_name – the endpoint name that triggered this query.
    api_method – the api method that triggered this query.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def create_patient_summary(therapist_id: str,
                                     patient_id: str,
                                     auth_manager: AuthManagerBaseClass,
                                     environment: str,
                                     session_id: str,
                                     endpoint_name: str,
                                     api_method: str,
                                     supabase_manager: SupabaseBaseClass):
        pass

    """
    Retrieves a set of questions to be presented as suggestions for the user on what to ask the assistant.

    Arguments:
    therapist_id – the id associated with the therapist user.
    patient_id – the id associated with the patient whose sessions will be used to fetch suggested questions.
    auth_manager – the auth_manager to be leveraged.
    environment – the current running environment.
    session_id – the current session id.
    endpoint_name – the endpoint name that triggered this query.
    api_method – the api method that triggered this query.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def fetch_question_suggestions(therapist_id: str,
                                         patient_id: str,
                                         auth_manager: AuthManagerBaseClass,
                                         environment: str,
                                         session_id: str,
                                         endpoint_name: str,
                                         api_method: str,
                                         supabase_manager: SupabaseBaseClass):
        pass

    """
    Updates a diarization entry with data coming from Speechmatics' notification service.
    Returns the session ID associated with the request.

    Arguments:
    auth_manager – the auth_manager to be leveraged.
    supabase_manager – the supabase manager to be leveraged internally.
    job_id – the id of the job that ran.
    summary – the session summary.
    diarization – the diarized session.
    """
    def update_diarization_with_notification_data(auth_manager: AuthManagerBaseClass,
                                                  supabase_manager: SupabaseBaseClass,
                                                  job_id: str,
                                                  diarization_summary: str,
                                                  diarization: str) -> str:
        pass

    """
    Returns a set of topics (along with frequency percentages) that the incoming patient_id is associated with.

    Arguments:
    therapist_id – the id associated with the therapist user.
    patient_id – the id associated with the patient whose sessions will be used to fetch suggested questions.
    auth_manager – the auth_manager to be leveraged.
    environment – the current running environment.
    session_id – the current session id.
    endpoint_name – the endpoint name that triggered this query.
    api_method – the api method that triggered this query.
    supabase_manager – the supabase manager to be leveraged internally.
    """
    async def fetch_frequent_topics(therapist_id: str,
                                    patient_id: str,
                                    auth_manager: AuthManagerBaseClass,
                                    environment: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    api_method: str,
                                    supabase_manager: SupabaseBaseClass):
        pass
