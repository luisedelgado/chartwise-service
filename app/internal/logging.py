import os

from ..managers.implementations.auth_manager import AuthManager

API_METHOD_POST = "post"
API_METHOD_PUT = "put"
API_METHOD_GET = "get"
API_METHOD_DELETE = "delete"

datastore_client = AuthManager().datastore_admin_instance()

"""
Logs data about an API request.

Arguments:
kwargs – the set of optional parameters to be sent into the method.
"""
def log_api_request(**kwargs):
    # We don't want to log if we're in staging or dev
    if os.environ.get("ENVIRONMENT").lower() != "prod":
        return

    try:
        session_id = None if "session_id" not in kwargs else kwargs["session_id"]
        endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
        description = None if "description" not in kwargs else kwargs["description"]
        auth_entity = None if "auth_entity" not in kwargs else kwargs["auth_entity"]
        therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
        patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
        method = None if "method" not in kwargs else kwargs["method"]
        datastore_client.table('api_request_logs').insert({
            "session_id": str(session_id),
            "endpoint_name": endpoint_name,
            "description": description,
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "method": method,
            "endpoint_auth_entity": auth_entity,
        }).execute()
    except Exception as e:
        print(f"Silently failing when trying to log request - Error: {str(e)}")

"""
Logs data about an API response.

Arguments:
kwargs – the set of associated optional args.
"""
def log_api_response(**kwargs):
    # We don't want to log if we're in staging or dev
    if os.environ.get("ENVIRONMENT").lower() != "prod":
        return

    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
    patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
    endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
    http_status_code = None if "http_status_code" not in kwargs else kwargs["http_status_code"]
    description = None if "description" not in kwargs else kwargs["description"]
    method = None if "method" not in kwargs else kwargs["method"]

    try:
        datastore_client.table('api_response_logs').insert({
            "session_id": str(session_id),
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "endpoint_name": endpoint_name,
            "http_status_code": http_status_code,
            "description": description,
            "method": method,
        }).execute()
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")

"""
Logs an error that happened during an API invocation.

Arguments:
kwargs – the set of associated optional args.
"""
def log_error(**kwargs):
    # We don't want to log if we're in staging or dev
    if os.environ.get("ENVIRONMENT").lower() != "prod":
        return

    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
    patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
    endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
    error_code = None if "error_code" not in kwargs else kwargs["error_code"]
    description = None if "description" not in kwargs else kwargs["description"]
    method = None if "method" not in kwargs else kwargs["method"]

    try:
        datastore_client.table('error_logs').insert({
            "session_id": str(session_id),
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "endpoint_name": endpoint_name,
            "error_code": error_code,
            "description": description,
            "method": method,
        }).execute()
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")

"""
Logs an event associated with a diarization operation.

Arguments:
kwargs – the set of associated optional args.
"""
def log_diarization_event(**kwargs):
    # We don't want to log if we're in staging or dev
    if os.environ.get("ENVIRONMENT").lower() != "prod":
        return

    error_code = None if "error_code" not in kwargs else kwargs["error_code"]
    description = None if "description" not in kwargs else kwargs["description"]

    try:
        datastore_client.table('diarization_logs').insert({
            "error_code": error_code,
            "description": description}).execute()
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")
