from . import library_clients

supabase_client = library_clients.supabase_admin_instance()

"""
Logs data about an API request.

Arguments:
session_id – the session id associated with the request.
endpoint_name – the endpoint name associated with the request.
"""
def log_api_request(session_id: str, endpoint_name: str, **kwargs):
    try:
        description = None if "description" not in kwargs else kwargs["description"]
        res = supabase_client.table('api_request_logs').insert({
            "session_id": str(session_id),
            "endpoint_name": endpoint_name,
            "description": description}).execute(),
        print(res)
    except Exception as e:
        print(e)

"""
Logs data about an API response.

Arguments:
kwargs – the set of associated optional args.
"""
def log_api_response(**kwargs):
    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
    patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
    endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
    http_status_code = None if "http_status_code" not in kwargs else kwargs["http_status_code"]
    description = None if "description" not in kwargs else kwargs["description"]

    try:
        res = supabase_client.table('api_response_logs').insert({
            "session_id": str(session_id),
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "endpoint_name": endpoint_name,
            "http_status_code": http_status_code,
            "description": description}).execute()
        print(res)
    except Exception as e:
        print(e)

"""
Logs an error that happened during an API invocation.

Arguments:
kwargs – the set of associated optional args.
"""
def log_error(**kwargs):
    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
    patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
    endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
    error_code = None if "error_code" not in kwargs else kwargs["error_code"]
    description = None if "description" not in kwargs else kwargs["description"]

    try:
        res = supabase_client.table('error_logs').insert({
            "session_id": str(session_id),
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "endpoint_name": endpoint_name,
            "error_code": error_code,
            "description": description}).execute()
        print(res)
    except Exception as e:
        print(e)
