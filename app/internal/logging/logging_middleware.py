import asyncio
import os
import time

from datetime import datetime, timedelta
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..internal_alert import EngineeringAlert
from ..schemas import PROD_ENVIRONMENT
from ...dependencies.dependency_container import (dependency_container, SupabaseBaseClass)
from ...managers.email_manager import EmailManager
from ...routers.assistant_router import AssistantRouter
from ...routers.audio_processing_router import AudioProcessingRouter
from ...routers.image_processing_router import ImageProcessingRouter

class TimingMiddleware(BaseHTTPMiddleware):

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

    def __init__(self, app):
        super().__init__(app)
        self.last_request_time = None

    async def dispatch(self, request: Request, call_next):
        # Detect stale data, and clear if needed
        if self.last_request_time is not None and (datetime.now() - self.last_request_time) > self.THIRTY_MIN_IDLE_THRESHOLD:
            print("Clearing stale data.")
            await dependency_container.inject_openai_client().clear_chat_history()
        self.last_request_time = datetime.now()

        start_time = time.perf_counter()
        request_url_path = request.url.path
        influx_client = dependency_container.inject_influx_client()

        environment = os.environ.get("ENVIRONMENT")
        if (environment == PROD_ENVIRONMENT
            and request_url_path not in self.IRRELEVANT_PATHS):
            await run_in_threadpool(influx_client.log_api_request,
                                    endpoint_name=request_url_path,
                                    method=request.method,
                                    session_id=request.cookies.get("session_id"))

        # Process the request and get the response
        response = await call_next(request)

        # Calculate the response time in milliseconds
        end_time = time.perf_counter()
        response_time = (end_time - start_time) * 1000

        session_id = getattr(request.state, self.SESSION_ID_KEY, None)
        therapist_id = getattr(request.state, self.THERAPIST_ID_KEY, None)
        patient_id = (getattr(request.state, self.PATIENT_ID_KEY, None)
                        or request.query_params.get(self.PATIENT_ID_KEY, None))

        if (environment == PROD_ENVIRONMENT
            and request_url_path not in self.IRRELEVANT_PATHS):
            await run_in_threadpool(influx_client.log_api_response,
                                    endpoint_name=request_url_path,
                                    method=request.method,
                                    response_time=response_time,
                                    status_code=response.status_code,
                                    session_id=session_id,
                                    session_report_id=getattr(request.state, self.SESSION_REPORT_ID_KEY, None),
                                    patient_id=patient_id,
                                    therapist_id=therapist_id)

        # Log PHI activity
        if (environment == PROD_ENVIRONMENT
            and request_url_path in self.PHI_ENDPOINTS):
            try:
                assert len(therapist_id or '') > 0, "Therapist ID is required."

                payload = {
                    "therapist_id": therapist_id,
                    "patient_id": patient_id,
                    "method": request.method,
                    "status_code": response.status_code,
                    "url_path": request_url_path,
                    "session_id": session_id,
                    "ip_address": request.headers.get("x-forwarded-for", request.client.host)
                }

                supabase_client: SupabaseBaseClass = dependency_container.inject_supabase_client_factory().supabase_admin_client()
                await run_in_threadpool(supabase_client.insert,
                                        table_name="audit_logs",
                                        payload=payload)
            except Exception as e:
                # Fail silently but send an internal alert.
                description = f"Failed to log PHI activity ({request.method} {request_url_path}). Exception raised: {str(e)}"
                asyncio.create_task(
                    EmailManager().send_internal_alert(
                        alert=EngineeringAlert(description=description,
                                               session_id=session_id,
                                               environment=environment,
                                               exception=e,
                                               therapist_id=therapist_id,
                                               patient_id=patient_id
                        )
                    )
                )
                pass

        return response
