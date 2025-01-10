import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ...dependencies.dependency_container import dependency_container

class TimingMiddleware(BaseHTTPMiddleware):

    IRRELEVANT_PATHS = ["/", "/openapi.json", "/docs", "/favicon.ico"]
    SESSION_ID_KEY = "session_id"
    SESSION_REPORT_ID_KEY = "session_report_id"
    PATIENT_ID_KEY = "patient_id"
    THERAPIST_ID_KEY = "therapist_id"

    def __init__(self, app):
        super().__init__(app)
        self.influx_client = dependency_container.inject_influx_client()

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        request_url_path = request.url.path
        if request_url_path not in self.IRRELEVANT_PATHS:
            self.influx_client.log_api_request(endpoint_name=request_url_path,
                                               method=request.method,
                                               session_id=request.cookies.get("session_id"))

        # Process the request and get the response
        response = await call_next(request)

        # Calculate the response time in milliseconds
        end_time = time.perf_counter()
        response_time = (end_time - start_time) * 1000

        if request_url_path not in self.IRRELEVANT_PATHS:
            self.influx_client.log_api_response(endpoint_name=request_url_path,
                                                method=request.method,
                                                response_time=response_time,
                                                status_code=response.status_code,
                                                session_id=getattr(request.state, self.SESSION_ID_KEY, None),
                                                session_report_id=getattr(request.state, self.SESSION_REPORT_ID_KEY, None),
                                                patient_id=getattr(request.state, self.PATIENT_ID_KEY, None),
                                                therapist_id=getattr(request.state, self.THERAPIST_ID_KEY, None))

        return response
