import os
import time

from datetime import datetime, timedelta
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..alerting.internal_alert import EngineeringAlert
from ..schemas import PROD_ENVIRONMENT
from ...dependencies.dependency_container import (dependency_container, AwsDbBaseClass)
from ...internal.utilities.general_utilities import retrieve_ip_address
from ...routers.assistant_router import AssistantRouter
from ...routers.audio_processing_router import AudioProcessingRouter
from ...routers.image_processing_router import ImageProcessingRouter

class TimingMiddleware(BaseHTTPMiddleware):

    VALID_API_METHODS = ["POST", "PUT", "GET", "DELETE"]
    PHI_ENDPOINTS = [AssistantRouter.PATIENTS_ENDPOINT,
                     AssistantRouter.SESSIONS_ENDPOINT,
                     AudioProcessingRouter.DIARIZATION_ENDPOINT,
                     AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                     ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT]
    IRRELEVANT_PATHS = ["/", "/openapi.json", "/docs", "/favicon.ico"]
    SESSION_ID_KEY = "session_id"
    SESSION_REPORT_ID_KEY = "session_report_id"
    PATIENT_ID_KEY = "patient_id"
    THERAPIST_ID_KEY = "therapist_id"
    THIRTY_MIN_IN_SECONDS = 1800
    THIRTY_MIN_IDLE_THRESHOLD = timedelta(seconds=THIRTY_MIN_IN_SECONDS)

    def __init__(
        self,
        app
    ):
        super().__init__(app)
        self.last_request_time = None

    async def dispatch(
        self,
        request: Request,
        call_next
    ):
        # Detect stale data, and clear if needed
        cls = type(self)
        if self.last_request_time is not None and (datetime.now() - self.last_request_time) > cls.THIRTY_MIN_IDLE_THRESHOLD:
            print("Clearing stale data.")
            await dependency_container.inject_openai_client().clear_chat_history()
        self.last_request_time = datetime.now()

        start_time = time.perf_counter()
        request_url_path = request.url.path
        request_method = request.method
        influx_client = dependency_container.inject_influx_client()

        environment = os.environ.get("ENVIRONMENT")
        if (environment == PROD_ENVIRONMENT
            and request_method in cls.VALID_API_METHODS
            and request_url_path not in cls.IRRELEVANT_PATHS):
            await run_in_threadpool(
                influx_client.log_api_request,
                endpoint_name=request_url_path,
                method=request_method,
                session_id=request.cookies.get(cls.SESSION_ID_KEY)
            )

        # Process the request and get the response
        response = await call_next(request)

        # Calculate the response time in milliseconds
        end_time = time.perf_counter()
        response_time = (end_time - start_time) * 1000

        session_id = getattr(
            request.state,
            cls.SESSION_ID_KEY,
            None
        )
        therapist_id = getattr(
            request.state,
            cls.THERAPIST_ID_KEY,
            None
        )
        patient_id = (
            getattr(
                request.state,
                cls.PATIENT_ID_KEY,
                None
            ) or request.query_params.get(
                cls.PATIENT_ID_KEY,
                None
            )
        )

        if (environment == PROD_ENVIRONMENT
            and request_method in cls.VALID_API_METHODS
            and request_url_path not in cls.IRRELEVANT_PATHS):
            await run_in_threadpool(
                influx_client.log_api_response,
                endpoint_name=request_url_path,
                method=request_method,
                response_time=response_time,
                status_code=response.status_code,
                session_id=session_id,
                session_report_id=getattr(
                    request.state,
                    cls.SESSION_REPORT_ID_KEY,
                    None
                ),
                patient_id=patient_id,
                therapist_id=therapist_id
            )

        # Log PHI activity
        if (environment == PROD_ENVIRONMENT
            and request_method in cls.VALID_API_METHODS
            and request_url_path in cls.PHI_ENDPOINTS):
            try:
                assert len(therapist_id or '') > 0, "Therapist ID is required."
            except Exception as e:
                # Not having a `therapist_id` at this point likely indicates the auth or
                # store tokens check failed. We can simply return the response since
                # we can't do audit logging without a `therapist_id`.
                return response

            try:
                payload = {
                    "therapist_id": therapist_id,
                    "patient_id": patient_id,
                    "method": request_method,
                    "status_code": response.status_code,
                    "url_path": request_url_path,
                    "session_id": session_id,
                    "ip_address": retrieve_ip_address(request),
                }

                aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
                await run_in_threadpool(
                    aws_db_client.insert,
                    user_id=therapist_id,
                    table_name="audit_logs",
                    payload=payload
                )
            except Exception as e:
                # Fail silently but send an internal alert.
                description = f"Failed to log PHI activity ({request.method} {request_url_path}). Exception raised: {str(e)}"
                dependency_container.inject_resend_client().send_internal_alert(
                    alert=EngineeringAlert(
                        description=description,
                        session_id=session_id,
                        environment=environment,
                        exception=e,
                        therapist_id=therapist_id,
                        patient_id=patient_id,
                    )
                )
                pass
        return response
