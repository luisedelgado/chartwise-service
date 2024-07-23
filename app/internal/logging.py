import os

from ..api.auth_base_class import AuthManagerBaseClass

class Logger:

    API_METHOD_POST = "post"
    API_METHOD_PUT = "put"
    API_METHOD_GET = "get"
    API_METHOD_DELETE = "delete"

    def __init__(self, auth_manager: AuthManagerBaseClass):
        self.auth_manager = auth_manager

    """
    Logs data about an API request.

    Arguments:
    kwargs – the set of optional parameters to be sent into the method.
    """
    def log_api_request(self, **kwargs):
        # We don't want to log if we're in staging or dev
        environment = os.environ.get("ENVIRONMENT").lower()
        if environment != "prod":
            return

        try:
            datastore_client = self.auth_manager.datastore_admin_instance()
            session_id = None if "session_id" not in kwargs else kwargs["session_id"]
            endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
            description = None if "description" not in kwargs else kwargs["description"]
            therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
            patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
            method = None if "method" not in kwargs else kwargs["method"]
            session_report_id = None if "session_report_id" not in kwargs else kwargs["session_report_id"]
            datastore_client.table('api_request_logs').insert({
                "session_id": str(session_id),
                "endpoint_name": endpoint_name,
                "description": description,
                "therapist_id": therapist_id,
                "patient_id": patient_id,
                "method": method,
                "session_report_id": session_report_id,
            }).execute()
        except Exception as e:
            print(f"Silently failing when trying to log request - Error: {str(e)}")

    """
    Logs data about an API response.

    Arguments:
    kwargs – the set of associated optional args.
    """
    def log_api_response(self, **kwargs):
        # We don't want to log if we're in staging or dev
        environment = os.environ.get("ENVIRONMENT").lower()
        if environment != "prod":
            return

        session_id = None if "session_id" not in kwargs else kwargs["session_id"]
        therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
        patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
        endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
        http_status_code = None if "http_status_code" not in kwargs else kwargs["http_status_code"]
        description = None if "description" not in kwargs else kwargs["description"]
        method = None if "method" not in kwargs else kwargs["method"]
        session_report_id = None if "session_report_id" not in kwargs else kwargs["session_report_id"]

        try:
            datastore_client = self.auth_manager.datastore_admin_instance()
            datastore_client.table('api_response_logs').insert({
                "session_id": str(session_id),
                "therapist_id": therapist_id,
                "patient_id": patient_id,
                "endpoint_name": endpoint_name,
                "http_status_code": http_status_code,
                "description": description,
                "method": method,
                "session_report_id": session_report_id,
            }).execute()
        except Exception as e:
            print(f"Silently failing when trying to log response - Error: {str(e)}")

    """
    Logs an error that happened during an API invocation.

    Arguments:
    kwargs – the set of associated optional args.
    """
    def log_error(self, **kwargs):
        # We don't want to log if we're in staging or dev
        environment = os.environ.get("ENVIRONMENT").lower()
        if environment != "prod":
            return

        session_id = None if "session_id" not in kwargs else kwargs["session_id"]
        therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
        patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
        endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
        error_code = None if "error_code" not in kwargs else kwargs["error_code"]
        description = None if "description" not in kwargs else kwargs["description"]
        method = None if "method" not in kwargs else kwargs["method"]
        session_report_id = None if "session_report_id" not in kwargs else kwargs["session_report_id"]

        try:
            datastore_client = self.auth_manager.datastore_admin_instance()
            datastore_client.table('error_logs').insert({
                "session_id": str(session_id),
                "therapist_id": therapist_id,
                "patient_id": patient_id,
                "endpoint_name": endpoint_name,
                "error_code": error_code,
                "description": description,
                "method": method,
                "session_report_id": session_report_id,
            }).execute()
        except Exception as e:
            print(f"Silently failing when trying to log response - Error: {str(e)}")

    """
    Logs an event associated with a diarization operation.

    Arguments:
    kwargs – the set of associated optional args.
    """
    def log_diarization_event(self, **kwargs):
        # We don't want to log if we're in staging or dev
        environment = os.environ.get("ENVIRONMENT").lower()
        if environment != "prod":
            return

        error_code = None if "error_code" not in kwargs else kwargs["error_code"]
        description = None if "description" not in kwargs else kwargs["description"]
        session_id = None if "session_id" not in kwargs else kwargs["session_id"]
        job_id = None if "job_id" not in kwargs else kwargs["job_id"]

        try:
            datastore_client = self.auth_manager.datastore_admin_instance()
            datastore_client.table('diarization_logs').insert({
                "error_code": error_code,
                "session_id": session_id,
                "job_id": job_id,
                "description": description}).execute()
        except Exception as e:
            print(f"Silently failing when trying to log response - Error: {str(e)}")

    """
    Event logged when a user deletes all their account data.

    Arguments:
    kwargs – the set of associated optional args.
    """
    def log_account_deletion(self, **kwargs):
        # We don't want to log if we're in staging or dev
        environment = os.environ.get("ENVIRONMENT").lower()
        if environment != "prod":
            return

        therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]

        try:
            datastore_client = self.auth_manager.datastore_admin_instance()
            datastore_client.table('account_deletion_logs').insert({
                "therapist_id": therapist_id,
            }).execute()
        except Exception as e:
            print(f"Silently failing when trying to log response - Error: {str(e)}")
