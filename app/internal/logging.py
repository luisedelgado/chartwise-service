import os

from fastapi import BackgroundTasks

from ..internal.dependency_container import dependency_container

API_METHOD_POST = "POST"
API_METHOD_PUT = "PUT"
API_METHOD_GET = "GET"
API_METHOD_DELETE = "DELETE"
SUCCESS_RESULT = "success"
FAILED_RESULT = "failed"

"""
Logs data about an API request.

Arguments:
background_tasks – object for scheduling concurrent tasks.
kwargs – the set of optional parameters to be sent into the method.
"""
def log_api_request(background_tasks: BackgroundTasks, **kwargs):
    # We don't want to log if we're in staging or dev
    environment = os.environ.get("ENVIRONMENT").lower()
    if environment != "prod":
        return

    try:
        session_id = None if "session_id" not in kwargs else kwargs["session_id"]
        endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
        description = None if "description" not in kwargs else kwargs["description"]
        therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
        patient_id = None if "patient_id" not in kwargs else kwargs["patient_id"]
        method = None if "method" not in kwargs else kwargs["method"]
        session_report_id = None if "session_report_id" not in kwargs else kwargs["session_report_id"]

        supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        background_tasks.add_task(supabase_client.insert,
                                    {
                                        "session_id": str(session_id),
                                        "endpoint_name": endpoint_name,
                                        "description": description,
                                        "therapist_id": therapist_id,
                                        "patient_id": patient_id,
                                        "method": method,
                                        "session_report_id": session_report_id,
                                    },
                                    "api_request_logs")
    except Exception as e:
        print(f"Silently failing when trying to log request - Error: {str(e)}")

"""
Logs data about an API response.

Arguments:
background_tasks – object for scheduling concurrent tasks.
kwargs – the set of associated optional args.
"""
def log_api_response(background_tasks: BackgroundTasks, **kwargs):
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
        supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        background_tasks.add_task(supabase_client.insert,
                                    {
                                        "session_id": str(session_id),
                                        "therapist_id": therapist_id,
                                        "patient_id": patient_id,
                                        "endpoint_name": endpoint_name,
                                        "http_status_code": http_status_code,
                                        "description": description,
                                        "method": method,
                                        "session_report_id": session_report_id,
                                    },
                                    "api_response_logs")
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")

"""
Logs an error that happened during an API invocation.

Arguments:
background_tasks – object for scheduling concurrent tasks.
kwargs – the set of associated optional args.
"""
def log_error(background_tasks: BackgroundTasks, **kwargs):
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
        supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        background_tasks.add_task(supabase_client.insert,
                                    {
                                        "session_id": str(session_id),
                                        "therapist_id": therapist_id,
                                        "patient_id": patient_id,
                                        "endpoint_name": endpoint_name,
                                        "error_code": error_code,
                                        "description": description,
                                        "method": method,
                                        "session_report_id": session_report_id,
                                    },
                                    "error_logs")
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")

"""
Logs an event associated with a textraction operation.

Arguments:
background_tasks – object for scheduling concurrent tasks.
kwargs – the set of associated optional args.
"""
def log_textraction_event(background_tasks: BackgroundTasks, **kwargs):
    # We don't want to log if we're in staging or dev
    environment = os.environ.get("ENVIRONMENT").lower()
    if environment != "prod":
        return

    therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
    error_code = None if "error_code" not in kwargs else kwargs["error_code"]
    description = None if "description" not in kwargs else kwargs["description"]
    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    job_id = None if "job_id" not in kwargs else kwargs["job_id"]

    try:
        supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        background_tasks.add_task(supabase_client.insert,
                                    {
                                        "therapist_id": therapist_id,
                                        "error_code": error_code,
                                        "session_id": session_id,
                                        "job_id": job_id,
                                        "description": description
                                    },
                                    "textraction_logs")
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")

"""
Event logged when a user deletes all their account data.

Arguments:
background_tasks – object for scheduling concurrent tasks.
kwargs – the set of associated optional args.
"""
def log_account_deletion(background_tasks: BackgroundTasks, **kwargs):
    # We don't want to log if we're in staging or dev
    environment = os.environ.get("ENVIRONMENT").lower()
    if environment != "prod":
        return

    therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]

    try:
        supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        background_tasks.add_task(supabase_client.insert,
                                    {
                                        "therapist_id": therapist_id,
                                    },
                                    "account_deletion_logs")
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")

"""
Logs data about a payment event.

Arguments:
background_tasks – object for scheduling concurrent tasks.
kwargs – the set of associated optional args.
"""
def log_payment_event(background_tasks: BackgroundTasks, **kwargs):
    # We don't want to log if we're in staging or dev
    environment = os.environ.get("ENVIRONMENT").lower()
    if environment != "prod":
        return

    therapist_id = None if "therapist_id" not in kwargs else kwargs["therapist_id"]
    event_name = None if "event_name" not in kwargs else kwargs["event_name"]
    customer_id = None if "customer_id" not in kwargs else kwargs["customer_id"]
    price_id = None if "price_id" not in kwargs else kwargs["price_id"]
    subscription_id = None if "subscription_id" not in kwargs else kwargs["subscription_id"]
    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    invoice_id = None if "invoice_id" not in kwargs else kwargs["invoice_id"]
    status = None if "status" not in kwargs else kwargs['status']
    message = None if "message" not in kwargs else kwargs['message']

    try:
        supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        background_tasks.add_task(supabase_client.insert,
                                    {
                                        "therapist_id": therapist_id,
                                        "event_name": event_name,
                                        "customer_id": customer_id,
                                        "price_id": price_id,
                                        "subscription_id": subscription_id,
                                        "session_id": session_id,
                                        "invoice_id": invoice_id,
                                        "status": status,
                                        "message": message,
                                    },
                                    "payment_activity")
    except Exception as e:
        print(f"Silently failing when trying to log response - Error: {str(e)}")

"""
Extracts metadata from incoming invoice `event`, and invokes a logging payment event.

Arguments:
event – the event containing the subscription data.
metadata – the metadata associated to the incoming event.
status – the event handling result status
background_tasks – the object with which to schedule concurrent operations.
message – the optional event handling result message
"""
def log_metadata_from_stripe_invoice_event(event,
                                           metadata: dict,
                                           status: str,
                                           background_tasks: BackgroundTasks,
                                           message: str = None):
    environment = os.environ.get("ENVIRONMENT").lower()
    if environment != "prod":
        return

    try:
        invoice = event['data']['object']
    except:
        return

    payment_event = None if 'type' not in event else event['type']
    therapist_id = None if 'therapist_id' not in metadata else metadata['therapist_id']
    session_id = None if 'session_id' not in metadata else metadata['session_id']
    invoice_id = None if 'id' not in metadata else metadata['id']
    customer_id = None if 'customer' not in invoice else invoice['customer']
    subscription_id = None if 'subscription' not in invoice else invoice['subscription']

    try:
        price_id = invoice["lines"]["data"][0]["price"]["id"]
    except:
        price_id = None

    log_payment_event(background_tasks=background_tasks,
                      therapist_id=therapist_id,
                      event_name=payment_event,
                      customer_id=customer_id,
                      price_id=price_id,
                      invoice_id = invoice_id,
                      subscription_id=subscription_id,
                      session_id=session_id,
                      status=status,
                      message=message,)

"""
Extracts metadata from incoming subscription `event`, and invokes a logging payment event.

Arguments:
event – the event containing the subscription data.
status – the event handling result status
background_tasks – the object with which to schedule concurrent operations.
message – the optional event handling result message
"""
def log_metadata_from_stripe_subscription_event(event,
                                                status: str,
                                                background_tasks: BackgroundTasks,
                                                message: str = None):
    environment = os.environ.get("ENVIRONMENT").lower()
    if environment != "prod":
        return

    subscription = event['data']['object']
    metadata = subscription.get('metadata', {})

    payment_event = None if 'type' not in event else event['type']
    therapist_id = None if 'therapist_id' not in metadata else metadata['therapist_id']
    session_id = None if 'session_id' not in metadata else metadata['session_id']
    customer_id = None if 'customer' not in subscription else subscription['customer']
    subscription_id = None if 'subscription' not in subscription else subscription['id']
    invoice_id = None if 'latest_invoice' not in subscription else subscription['latest_invoice']

    try:
        price_id = subscription["items"]["data"][0]["price"]["id"]
    except:
        price_id = None

    log_payment_event(background_tasks=background_tasks,
                      therapist_id=therapist_id,
                      event_name=payment_event,
                      customer_id=customer_id,
                      price_id=price_id,
                      message=message,
                      status=status,
                      subscription_id=subscription_id,
                      session_id=session_id,
                      invoice_id=invoice_id)
